# Acumatica Quality Management System (QMS) Extension Specification
## Minimum Technical Specification for Acumatica Cloud xRP Framework Customization Package

---

## 1. Executive Summary & Purpose

### 1.1 Purpose
Standard Acumatica Cloud ERP does not ship with a native Quality Management module in its out-of-the-box Distribution or Manufacturing editions. To support automated Certificate of Analysis (CoA) ingestion, receiving dock quarantine, tolerance validation, and automated lot dispositioning, this specification defines the **minimum viable Acumatica xRP extension** (`CanNordic.QMS`).

This extension provides the database tables, Data Access Classes (DACs), Business Logic Controllers (Graphs), Web Service Endpoints, and UI screens required to implement the integration architecture detailed in `acumatica/acumatica_integration_matrix.md` and regulatory mandates under **Health Canada GMP (GUI-0001 / GUI-0158)** and **21 CFR Part 11**.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                CANNORDIC.QMS EXTENSION ARCHITECTURE                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                     │
 1. RECEIVING DOCK PO RECEIPT                        ▼
 ┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ • Standard `POReceiptEntry` intercepted via graph extension `POReceiptEntry_Extension`.               │
 │ • On PO Receipt release:                                                                              │
 │   - Identifies items flagged with `UsrQMSInspectionRequired = true`.                                  │
 │   - Sets `INLotSerialStatus.LotStatus` to 'QC Hold' (locked from BOM allocation).                    │
 │   - Auto-generates draft `QMSInspectionOrder` populated with Plan ID, Lot, Vendor, and Receipt ID.    │
 └───────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                     │
 2. COA INGESTION VIA REST API                       ▼
 ┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ • Ingestion Engine posts analytical results to custom REST endpoint `/entity/QMS/22.200.001/`.        │
 │ • Updates `QMSInspectionOrder` test result rows with actual values and laboratory certificate metadata.│
 │ • Attaches original PDF CoA and JSON audit payload via Acumatica `/files` endpoint.                  │
 └───────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                     │
 3. EVALUATION & LOT STATUS TRANSITION               ▼
 ┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ • `QMSInspectionOrderEntry` executes tolerance validation against `QMSInspectionPlan`:                 │
 │   - Checks numeric bounds: `MinValue <= ActualNumericValue <= MaxValue`.                              │
 │   - Checks text parameters (e.g., pathogen absence, visual appearance).                               │
 │   - Checks shelf-life requirement: `ExpiryDate >= ReceiptDate + MinShelfLifeDays`.                   │
 └───────────────────────────────────┬───────────────────────────────────┬───────────────────────────────┘
                                     │                                   │
                           [ALL PARAMETERS PASS]               [ANY PARAMETER FAILS]
                                     │                                   │
                                     ▼                                   ▼
 ┌───────────────────────────────────────────────────────┐ ┌───────────────────────────────────────────┐
 │ • `QMSInspectionOrder.OverallEvaluation = 'Pass'`     │ │ • `QMSInspectionOrder.OverallEvaluation`    │
 │ • `INLotSerialStatus.LotStatus = 'Released'`          │ │   = 'Fail'                                  │
 │ • Inventory unblocked for production work orders      │ │ • `INLotSerialStatus.LotStatus`             │
 │                                                       │ │   = 'Quarantine'                            │
 │                                                       │ │ • Auto-creates `QMSNonConformance` (NCR)   │
 │                                                       │ │ • Alerts QA Officer & halts allocation      │
 └───────────────────────────────────────────────────────┘ └───────────────────────────────────────────┘
```

---

## 2. Core Entities & Data Access Classes (DACs)

The extension introduces three primary custom entities, one setup entity, and one DAC extension on standard inventory.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   ENTITY RELATIONSHIP DIAGRAM (ERD)                                     │
├───────────────────────────────┬───────────────────────────────────┬─────────────────────────────────────┤
│ HEADER DAC                    │ LINE / DETAIL DAC                 │ RELATED STANDARD DACS               │
├───────────────────────────────┼───────────────────────────────────┼─────────────────────────────────────┤
│ `QMSInspectionPlan`           │ `QMSInspectionPlanTest`           │ `InventoryItem` (Item Master)       │
│ (Quality Inspection Specs)    │ (Individual test limits & methods)│                                     │
├───────────────────────────────┼───────────────────────────────────┼─────────────────────────────────────┤
│ `QMSInspectionOrder`          │ `QMSInspectionOrderResult`        │ `POReceipt` (Dock Receipt)          │
│ (Inspection Execution Record) │ (Actual parsed lab test results)  │ `INLotSerialStatus` (Lot Record)    │
│                               │                                   │ `Vendor` (Supplier Master)          │
├───────────────────────────────┼───────────────────────────────────┼─────────────────────────────────────┤
│ `QMSNonConformance`           │ N/A (Header ticket)               │ `QMSInspectionOrder`                │
│ (NCR & Quarantine Ticket)     │                                   │ `INLotSerialStatus` (Quarantine Lot)│
└───────────────────────────────┴───────────────────────────────────┴─────────────────────────────────────┘
```

---

### 2.1 DAC 1: `QMSInspectionPlan` (Inspection Plan Master)
Defines the required analytical testing specifications and acceptable ranges for an inventory item.

* **Database Table:** `UsrQMSInspectionPlan`
* **DAC Name:** `CanNordic.QMS.QMSInspectionPlan`

| Field Name | Type | Key | Description / Constraints |
| :--- | :--- | :---: | :--- |
| `PlanID` | `PXDBString(30, IsUnicode = true)` | **PK** | Unique Plan ID (e.g., `QPLAN-BOT-ECH4`). |
| `Description` | `PXDBString(255, IsUnicode = true)`| | Human-readable title of the quality inspection plan. |
| `InventoryID` | `PXDBInt()` | FK | Foreign key to standard `InventoryItem.inventoryID`. |
| `SamplingPlan`| `PXDBString(100, IsUnicode = true)`| | Sampling standard (e.g., `ISO 2859-1 Level II Normal`). |
| `Status` | `PXDBString(1)` | | Status: `A` (Active), `H` (Hold), `I` (Inactive). |
| `RevisionID` | `PXDBInt()` | | Version/Revision integer counter (default: 1). |
| `EffectiveDate`| `PXDBDate()` | | Date from which the plan is legally effective. |
| `NoteID` | `PXNote()` | | Acumatica Note & File attachment link GUID. |
| *Audit Fields*| `CreatedByID`, `CreatedDateTime`, `LastModifiedByID`, `LastModifiedDateTime` | | Standard Acumatica system audit trail fields. |

---

### 2.2 DAC 2: `QMSInspectionPlanTest` (Plan Test Criteria Line)
Defines individual parameter tolerances, target values, analytical methods, and criticality.

* **Database Table:** `UsrQMSInspectionPlanTest`
* **DAC Name:** `CanNordic.QMS.QMSInspectionPlanTest`

| Field Name | Type | Key | Description / Constraints |
| :--- | :--- | :---: | :--- |
| `PlanID` | `PXDBString(30, IsUnicode = true)` | **PK, FK** | Parent reference to `QMSInspectionPlan.PlanID`. |
| `LineNbr` | `PXDBInt()` | **PK** | Line sequence integer (10, 20, 30...). |
| `TestID` | `PXDBString(30, IsUnicode = true)` | | Test code (e.g., `ASSAY_POLYPHENOLS`, `HM_LEAD`, `MICRO_TAMC`). |
| `Description` | `PXDBString(120, IsUnicode = true)`| | Test description (e.g., `Elemental Impurities: Lead (Pb)`). |
| `TestMethod` | `PXDBString(100, IsUnicode = true)`| | Analytical standard (e.g., `ICP-MS (USP <2232>)`). |
| `TargetValue` | `PXDBDecimal(4)` | | Target nominal value (nullable). |
| `MinValue` | `PXDBDecimal(4)` | | Allowable lower bound (nullable for upper-limit tests). |
| `MaxValue` | `PXDBDecimal(4)` | | Allowable upper bound (nullable for assay minimums). |
| `UOM` | `PXDBString(20, IsUnicode = true)` | | Standard SI unit of measure (`% (w/w)`, `ppm`, `CFU/g`). |
| `Criticality` | `PXDBString(1)` | | `C` (Critical), `M` (Major), `m` (Minor). Default: `C`. |
| `IsRequired` | `PXDBBool()` | | Must be present on CoA to allow release. Default: `true`. |

---

### 2.3 DAC 3: `QMSInspectionOrder` (Inspection Order Header)
Represents the quality evaluation lifecycle for a specific received batch/lot.

* **Database Table:** `UsrQMSInspectionOrder`
* **DAC Name:** `CanNordic.QMS.QMSInspectionOrder`

| Field Name | Type | Key | Description / Constraints |
| :--- | :--- | :---: | :--- |
| `InspectionOrderNbr` | `PXDBString(15, IsUnicode = true)` | **PK** | Auto-numbered identifier (`QORD-000001`). AutoNumbering rule. |
| `Status` | `PXDBString(1)` | | `O` (Open / Pending Ingestion), `C` (Completed), `X` (Cancelled). |
| `InventoryID` | `PXDBInt()` | FK | Foreign key to `InventoryItem.inventoryID`. |
| `LotSerialNbr` | `PXDBString(50, IsUnicode = true)` | | Received lot or batch number. |
| `VendorID` | `PXDBInt()` | FK | Foreign key to `BAccount.bAccountID` (Vendor). |
| `ReceiptNbr` | `PXDBString(15, IsUnicode = true)` | FK | Foreign key to `POReceipt.receiptNbr`. |
| `PlanID` | `PXDBString(30, IsUnicode = true)` | FK | Foreign key to `QMSInspectionPlan.planID`. |
| `TestingLabID`| `PXDBString(30, IsUnicode = true)`| | Testing lab code (e.g., `LAB-GL-ANALYTICAL`). |
| `LabCertificateNbr`| `PXDBString(60, IsUnicode = true)`| | CoA document certificate number from lab. |
| `InspectionDate` | `PXDBDate()` | | Date of inspection evaluation. |
| `OverallEvaluation` | `PXDBString(1)` | | `P` (Pending), `V` (Pass / Validated), `F` (Fail / OOS). |
| `EvaluatedByID` | `PXDBGuid()` | | User GUID who approved or executed the AI evaluation. |
| `EvaluationDateTime`| `PXDBDateAndTime()` | | Precise timestamp of evaluation completion. |
| `NoteID` | `PXNote()` | | Attachment link for verified PDF & JSON payload. |

---

### 2.4 DAC 4: `QMSInspectionOrderResult` (Inspection Test Result Line)
Stores actual laboratory analytical results extracted from the CoA against plan criteria.

* **Database Table:** `UsrQMSInspectionOrderResult`
* **DAC Name:** `CanNordic.QMS.QMSInspectionOrderResult`

| Field Name | Type | Key | Description / Constraints |
| :--- | :--- | :---: | :--- |
| `InspectionOrderNbr` | `PXDBString(15, IsUnicode = true)` | **PK, FK** | Parent reference to `QMSInspectionOrder.InspectionOrderNbr`. |
| `LineNbr` | `PXDBInt()` | **PK** | Sequence number matching `QMSInspectionPlanTest.LineNbr`. |
| `TestID` | `PXDBString(30, IsUnicode = true)` | | Test identifier. |
| `TestMethod` | `PXDBString(100, IsUnicode = true)`| | Verified analytical method reported by laboratory. |
| `TargetSpec` | `PXDBString(60, IsUnicode = true)` | | Textual specification string (e.g., `<= 0.50 ppm`). |
| `ActualNumericValue`| `PXDBDecimal(4)` | | Normalized numeric result in standard SI units (nullable). |
| `ActualTextValue` | `PXDBString(100, IsUnicode = true)`| | Full textual result string (e.g., `Absent in 10g` or `0.084 ppm`). |
| `Evaluation` | `PXDBString(1)` | | Line disposition: `P` (Pass), `F` (Fail), `S` (Skipped). |
| `Notes` | `PXDBString(255, IsUnicode = true)`| | Auditor or AI anomaly notes (e.g., UoM converted from ppb). |

---

### 2.5 DAC 5: `QMSNonConformance` (Non-Conformance Report / NCR)
Captures out-of-specification failures, quarantine segregation, and corrective action workflows.

* **Database Table:** `UsrQMSNonConformance`
* **DAC Name:** `CanNordic.QMS.QMSNonConformance`

| Field Name | Type | Key | Description / Constraints |
| :--- | :--- | :---: | :--- |
| `NCRNbr` | `PXDBString(15, IsUnicode = true)` | **PK** | Auto-numbered ticket identifier (`QNCR-000001`). |
| `Status` | `PXDBString(1)` | | `O` (Open), `I` (In Investigation), `C` (Closed), `V` (Void). |
| `InspectionOrderNbr` | `PXDBString(15, IsUnicode = true)`| FK | Linked inspection order. |
| `InventoryID` | `PXDBInt()` | FK | Foreign key to `InventoryItem`. |
| `LotSerialNbr` | `PXDBString(50, IsUnicode = true)` | | Contaminated or OOS lot number. |
| `VendorID` | `PXDBInt()` | FK | Foreign key to `Vendor`. |
| `ReceiptNbr` | `PXDBString(15, IsUnicode = true)` | FK | Foreign key to `POReceipt`. |
| `Severity` | `PXDBString(1)` | | `C` (Critical), `M` (Major), `m` (Minor). |
| `NonConformanceType` | `PXDBString(60, IsUnicode = true)` | | Category (e.g., `Chemical Contamination / Heavy Metals`). |
| `RootCauseCategory` | `PXDBString(60, IsUnicode = true)` | | Cause classification (e.g., `Supplier Raw Material Contamination`). |
| `AssignedQAOfficer` | `PXDBGuid()` | | User GUID of assigned QA investigator. |
| `Description` | `PXDBString(1000, IsUnicode = true)`| | Detailed description of OOS failure and limits breached. |
| `ActionRequired` | `PXDBString(255, IsUnicode = true)`| | Remedial action (e.g., `Quarantine Segregation & RTV Claim`). |
| `InventoryHoldStatus`| `PXDBString(10)` | | ERP lot hold status code (`Quarantine` or `Rejected`). |
| `NoteID` | `PXNote()` | | Acumatica Note & File attachment link GUID. |

---

### 2.6 DAC Extension: `InventoryItem` (Stock Item Master Extension)
Extends Acumatica's standard `PX.Objects.IN.InventoryItem` DAC to flag items subject to mandatory QMS inspection.

* **Class Name:** `CanNordic.QMS.InventoryItemExt : PXCacheExtension<InventoryItem>`

```csharp
public class InventoryItemExt : PXCacheExtension<InventoryItem>
{
    // UsrQMSInspectionRequired: Enables dock auto-hold and QMS order generation
    #region UsrQMSInspectionRequired
    [PXDBBool]
    [PXDefault(false)]
    [PXUIField(DisplayName = "Requires Quality Inspection")]
    public virtual bool? UsrQMSInspectionRequired { get; set; }
    public abstract class usrQMSInspectionRequired : PX.Data.BQL.BqlBool.Field<usrQMSInspectionRequired> {}
    #endregion

    // UsrQMSInspectionPlanID: Default Quality Plan ID linked to this SKU
    #region UsrQMSInspectionPlanID
    [PXDBString(30, IsUnicode = true)]
    [PXSelector(typeof(Search<QMSInspectionPlan.planID, 
        Where<QMSInspectionPlan.status, Equal<QMSInspectionPlanStatus.active>>>),
        DescriptionField = typeof(QMSInspectionPlan.description))]
    [PXUIField(DisplayName = "Inspection Plan")]
    public virtual string UsrQMSInspectionPlanID { get; set; }
    public abstract class usrQMSInspectionPlanID : PX.Data.BQL.BqlString.Field<usrQMSInspectionPlanID> {}
    #endregion

    // UsrMinShelfLifeDays: Minimum shelf life required upon warehouse arrival
    #region UsrMinShelfLifeDays
    [PXDBInt]
    [PXDefault(0)]
    [PXUIField(DisplayName = "Min. Receiving Shelf Life (Days)")]
    public virtual int? UsrMinShelfLifeDays { get; set; }
    public abstract class usrMinShelfLifeDays : PX.Data.BQL.BqlInt.Field<usrMinShelfLifeDays> {}
    #endregion
}
```

---

## 3. Business Logic Controllers (Graphs) & Automation Workflows

### 3.1 Graph 1: `QMSInspectionPlanMaint` (`QM.20.10.00`)
Standard primary graph for authoring and maintaining item inspection plans.

* **Base Class:** `PXGraph<QMSInspectionPlanMaint, QMSInspectionPlan>`
* **Views:**
  * `PXSelect<QMSInspectionPlan, Where<QMSInspectionPlan.planID, Equal<Current<QMSInspectionPlan.planID>>>> Document;`
  * `PXSelect<QMSInspectionPlanTest, Where<QMSInspectionPlanTest.planID, Equal<Current<QMSInspectionPlan.planID>>>, OrderBy<Asc<QMSInspectionPlanTest.lineNbr>>> Tests;`
* **Validation Rules:**
  * If `MinValue` is provided and `MaxValue` is provided, `MinValue` must be $\le$ `MaxValue`.
  * `PlanID` must be unique and uppercase.

---

### 3.2 Graph 2: `QMSInspectionOrderEntry` (`QM.30.10.00`)
The primary operational graph that records actual test results, executes tolerance validation, and flips lot status.

* **Base Class:** `PXGraph<QMSInspectionOrderEntry, QMSInspectionOrder>`
* **Views:**
  * `PXSelect<QMSInspectionOrder, Where<QMSInspectionOrder.inspectionOrderNbr, Equal<Current<QMSInspectionOrder.inspectionOrderNbr>>>> Document;`
  * `PXSelect<QMSInspectionOrderResult, Where<QMSInspectionOrderResult.inspectionOrderNbr, Equal<Current<QMSInspectionOrder.inspectionOrderNbr>>>> Results;`

#### Key Action 1: `EvaluateResults`
Iterates through all `QMSInspectionOrderResult` lines and compares them against the linked `QMSInspectionPlanTest` limits:
1. **Numeric Tests:**
   * If `MinValue` is set and `ActualNumericValue < MinValue` $\rightarrow$ Mark Line **Fail**.
   * If `MaxValue` is set and `ActualNumericValue > MaxValue` $\rightarrow$ Mark Line **Fail**.
   * Otherwise $\rightarrow$ Mark Line **Pass**.
2. **Text / Qualitative Tests:**
   * Evaluates text string (e.g., checks for presence of substring `"Absent"` or `"Negative"` for pathogens).
3. **Rollup Evaluation:**
   * If any line fails $\rightarrow$ `OverallEvaluation = 'Fail'`.
   * If all lines pass $\rightarrow$ `OverallEvaluation = 'Pass'`.

#### Key Action 2: `ReleaseLotDecision` (Lot Status Transition)
Invoked automatically or by QA Officer sign-off:
* **Green Path (`Pass`):**
  ```csharp
  // Updates Acumatica standard INLotSerialStatus
  INLotSerialStatus lotStatus = PXSelect<INLotSerialStatus,
      Where<INLotSerialStatus.inventoryID, Equal<Required<INLotSerialStatus.inventoryID>>,
        And<INLotSerialStatus.lotSerialNbr, Equal<Required<INLotSerialStatus.lotSerialNbr>>>>>
      .Select(this, order.InventoryID, order.LotSerialNbr);

  if (lotStatus != null)
  {
      lotStatus.LotStatus = "Released"; // Standard active status
      Caches[typeof(INLotSerialStatus)].Update(lotStatus);
  }
  order.Status = QMSOrderStatus.Completed;
  ```
* **Red Path (`Fail` / OOS):**
  ```csharp
  // Updates lot to Quarantine and raises NCR
  if (lotStatus != null)
  {
      lotStatus.LotStatus = "Quarantine"; // Hold status
      Caches[typeof(INLotSerialStatus)].Update(lotStatus);
  }
  // Auto-generate Non-Conformance Record
  QMSNonConformanceEntry ncrGraph = PXGraph.CreateInstance<QMSNonConformanceEntry>();
  QMSNonConformance ncr = ncrGraph.Document.Insert();
  ncr.InspectionOrderNbr = order.InspectionOrderNbr;
  ncr.InventoryID = order.InventoryID;
  ncr.LotSerialNbr = order.LotSerialNbr;
  ncr.VendorID = order.VendorID;
  ncr.ReceiptNbr = order.ReceiptNbr;
  ncr.Severity = QMSSeverity.Critical;
  ncr.Description = "Automated OOS Failure: Laboratory results breached acceptable tolerances.";
  ncrGraph.Save.Press();
  ```

---

### 3.3 Graph 3: `QMSNonConformanceEntry` (`QM.30.20.00`)
Maintenance graph for managing quarantine items, root cause analysis, and disposition (Return to Vendor / Scrap / Deviation).

* **Base Class:** `PXGraph<QMSNonConformanceEntry, QMSNonConformance>`
* **Actions:**
  * `CloseNCR`: Verifies formal root cause documentation before resolving ticket.
  * `DispositionRTV`: Links directly to Acumatica `POReceiptEntry` Return to Vendor flow.

---

### 3.4 Graph Extension: `POReceiptEntry_Extension` (Dock Arrival Auto-Hold)
Intercepts the Acumatica Purchasing receipt release process to guarantee regulatory quarantine upon physical goods arrival.

* **Target Graph:** `PX.Objects.PO.POReceiptEntry`

```csharp
public class POReceiptEntry_Extension : PXGraphExtension<POReceiptEntry>
{
    [PXOverride]
    public delegate void ReleaseDelegate(POReceipt doc);

    [PXOverride]
    public void Release(POReceipt doc, ReleaseDelegate baseMethod)
    {
        // 1. Execute standard Acumatica receipt posting
        baseMethod(doc);

        // 2. Scan lines for items requiring QMS inspection
        foreach (POReceiptLine line in Base.receiptLines.Select())
        {
            InventoryItem item = PXSelect<InventoryItem, 
                Where<InventoryItem.inventoryID, Equal<Required<InventoryItem.inventoryID>>>>
                .Select(Base, line.InventoryID);

            InventoryItemExt itemExt = item?.GetExtension<InventoryItemExt>();
            if (itemExt?.UsrQMSInspectionRequired == true)
            {
                // Iterate through lot allocations
                foreach (POReceiptLineSplit split in PXSelect<POReceiptLineSplit,
                    Where<POReceiptLineSplit.receiptNbr, Equal<Required<POReceiptLineSplit.receiptNbr>>,
                      And<POReceiptLineSplit.lineNbr, Equal<Required<POReceiptLineSplit.lineNbr>>>>>
                    .Select(Base, line.ReceiptNbr, line.LineNbr))
                {
                    // A. Force lot status to 'QC Hold'
                    UpdateLotStatus(item.InventoryID, split.LotSerialNbr, "QC Hold");

                    // B. Auto-generate draft QMSInspectionOrder
                    CreateDraftInspectionOrder(doc, line, split, itemExt.UsrQMSInspectionPlanID);
                }
            }
        }
    }
}
```

---

## 4. REST API Custom Web Service Endpoint (`QMS/22.200.001`)

Under the Acumatica **Web Service Endpoints (`SM207060`)** screen, the customization package registers the custom endpoint `QMS/22.200.001` to expose these entities to the Ingestion Engine:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   QMS REST WEB SERVICE ENDPOINT CONTRACT                                │
├───────────────────────┬──────────────────────────┬──────────────┬───────────────────────────────────────┤
│ ENDPOINT ENTITY       │ MAPPED DAC               │ HTTP VERBS   │ INTENDED FUNCTION                     │
├───────────────────────┼──────────────────────────┼──────────────┼───────────────────────────────────────┤
│ `InspectionPlan`      │ `QMSInspectionPlan`      │ `GET`        │ Query target specs & test criteria    │
├───────────────────────┼──────────────────────────┼──────────────┼───────────────────────────────────────┤
│ `InspectionOrder`     │ `QMSInspectionOrder`     │ `GET, PUT`   │ Ingest laboratory CoA results         │
├───────────────────────┼──────────────────────────┼──────────────┼───────────────────────────────────────┤
│ `NonConformance`      │ `QMSNonConformance`      │ `GET, POST`  │ Log OOS defect tickets                │
└───────────────────────┴──────────────────────────┴──────────────┴───────────────────────────────────────┘
```

### 4.1 Endpoint Schema: `InspectionPlan`
* **GET Path:** `/entity/QMS/22.200.001/InspectionPlan?$filter=PlanID eq 'QPLAN-BOT-ECH4'&$expand=Tests`
* **Fields:**
  * `PlanID` (String)
  * `Description` (String)
  * `InventoryID` (String)
  * `SamplingPlan` (String)
  * `Status` (String)
  * `Tests` (List of Test Objects):
    * `LineNbr` (Int)
    * `TestID` (String)
    * `Description` (String)
    * `TestMethod` (String)
    * `TargetValue` (Decimal)
    * `MinValue` (Decimal)
    * `MaxValue` (Decimal)
    * `UOM` (String)
    * `Criticality` (String)

### 4.2 Endpoint Schema: `InspectionOrder`
* **PUT Path:** `/entity/QMS/22.200.001/InspectionOrder`
* **Fields:**
  * `InspectionOrderNbr` (String - Empty for new or populated to update existing draft)
  * `InventoryID` (String)
  * `LotSerialNbr` (String)
  * `VendorID` (String)
  * `ReceiptNbr` (String)
  * `PlanID` (String)
  * `TestingLabID` (String)
  * `LabCertificateNbr` (String)
  * `InspectionDate` (DateTime)
  * `OverallEvaluation` (String: `Pass` or `Fail`)
  * `Results` (List of Result Objects):
    * `LineNbr` (Int)
    * `TestID` (String)
    * `TestMethod` (String)
    * `TargetSpec` (String)
    * `ActualNumericValue` (Decimal)
    * `ActualTextValue` (String)
    * `Evaluation` (String: `Pass` or `Fail`)
    * `Notes` (String)

### 4.3 Endpoint Schema: `NonConformance`
* **POST Path:** `/entity/QMS/22.200.001/NonConformance`
* **Fields:**
  * `NCRNbr` (String - Auto-assigned)
  * `InspectionOrderNbr` (String)
  * `InventoryID` (String)
  * `LotSerialNbr` (String)
  * `VendorID` (String)
  * `ReceiptNbr` (String)
  * `Severity` (String: `Critical`, `Major`, `Minor`)
  * `NonConformanceType` (String)
  * `RootCauseCategory` (String)
  * `Description` (String)
  * `ActionRequired` (String)
  * `InventoryHoldStatus` (String: `Quarantine`)

---

## 5. Screen Layouts & Site Map Navigation

The customization package installs screens under the new **Quality Management** workspace:

```
Acumatica Modern UI Site Map
└── Quality Management (QM)
    ├── Configuration
    │   └── Quality Preferences             -> QM.10.10.00 (QMSSetupMaint)
    ├── Master Data
    │   └── Inspection Plans                -> QM.20.10.00 (QMSInspectionPlanMaint)
    └── Transactions
        ├── Inspection Orders               -> QM.30.10.00 (QMSInspectionOrderEntry)
        └── Non-Conformance Reports (NCR)   -> QM.30.20.00 (QMSNonConformanceEntry)
```

### 5.1 Screen QM.20.10.00: Inspection Plans
* **Summary Area:** `PlanID`, `Description`, `InventoryID`, `SamplingPlan`, `Status`, `EffectiveDate`.
* **Grid Area (`Tests`):** Columns for `LineNbr`, `TestID`, `Description`, `TestMethod`, `TargetValue`, `MinValue`, `MaxValue`, `UOM`, `Criticality`.

### 5.2 Screen QM.30.10.00: Inspection Orders
* **Summary Area:** `InspectionOrderNbr`, `Status`, `InventoryID`, `LotSerialNbr`, `VendorID`, `ReceiptNbr`, `TestingLabID`, `LabCertificateNbr`, `OverallEvaluation`.
* **Action Buttons in Toolbar:**
  * **Evaluate:** Runs validation rules on all lines and calculates `OverallEvaluation`.
  * **Release Lot:** Completes order and promotes lot status to `Released`.
  * **Quarantine Lot & Raise NCR:** Completes order as failed, moves lot to `Quarantine`, and opens NCR.
* **Grid Area (`Results`):** Columns for `LineNbr`, `TestID`, `TestMethod`, `TargetSpec`, `ActualNumericValue`, `ActualTextValue`, `Evaluation`, `Notes`.

---

## 6. Regulatory & Audit Trail Compliance (Health Canada GMP GUI-0001 / GUI-0158)

To satisfy Health Canada requirements for computer-assisted raw material release:

1. **Immutable System Audit Fields:**
   * Every modification to `QMSInspectionPlan` and `QMSInspectionOrder` records `CreatedByID`, `CreatedDateTime`, `LastModifiedByID`, and `LastModifiedDateTime`.
   * Evaluation completion permanently stamps `EvaluatedByID` and `EvaluationDateTime`.
2. **Document Linkage Provenance:**
   * The original laboratory CoA PDF and the parsed JSON evaluation payload must be attached to the `QMSInspectionOrder` record via the standard Acumatica Note & File link mechanism (`NoteID`).
   * Dock clerks and Quality Auditors can click the paperclip attachment icon on either the `QMSInspectionOrder` or `INLotSerialStatus` screen to view the original PDF document.
3. **Electronic Signature / Disposition Accountability:**
   * Release of material from `QC Hold` to `Released` requires either an automated token from the verified Ingestion Engine service account or an authenticated QA user possessing the `Quality Manager` role in Acumatica.

---

## 7. Customization Package Delivery Manifest

The customization package is delivered as a standard Acumatica Customization Project (`.zip`):

```
CanNordic_QMS_Customization.zip
├── _project/
│   └── ProjectMetadata.xml             <- Package manifest, version 22.200.001
├── Cst_App/
│   └── bin/
│       └── CanNordic.QMS.dll           <- Compiled C# assemblies (DACs, Graphs, Extensions)
├── Pages_QM/
│   ├── QM101000.aspx                   <- Quality Preferences
│   ├── QM201000.aspx                   <- Inspection Plans
│   ├── QM301000.aspx                   <- Inspection Orders
│   └── QM302000.aspx                   <- Non-Conformance Reports
└── Scripts/
    └── CreateQMSTables.sql             <- SQL DDL scripts for UsrQMS* tables
```

This specification provides the minimal, self-contained, and production-compliant technical blueprint for deploying the native Acumatica QMS extension required by this repository.
