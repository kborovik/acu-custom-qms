# Acumatica 2026 R1: Modern UI Customization Patterns & Architecture Analysis

## 1. Executive Summary & Strategic Context

Acumatica's transition from the legacy ASP.NET Web Forms interface (**Classic UI**) to the TypeScript- and Aurelia-powered single-page application framework (**Modern UI**) reaches a critical turning point in **2026 R1**:

- **Mandatory Transition Ahead (2026 R2 Deprecation)**: Acumatica officially announced that the Classic UI is deprecated and will be removed in **2026 R2**.
  Starting in 2026 R2, users and administrators will no longer have the option to toggle back to Classic UI (`SM200505`).
- **Modern UI as Default in 2026 R1**: All new instances and tenant implementations in 2026 R1 run Modern UI by default.
  All ISV solutions and custom development must conform to Modern UI patterns to maintain forward compatibility.
- **Key 2026 R1 Platform Advances**:
  - **Development Folder Synchronization**: Direct compilation and bi-directional file synchronization between the local file system (`FrontendSources\screen\src\development\`) and the customization project package.
  - **In-Browser Modern UI Editor (`AU201080`)**: Visual editing, code comparison, and automated TypeScript/HTML extension generation directly inside the Customization Project Editor.
  - **Dedicated Modern UI Patching Mechanism**: Isolated runtime patching for frontend issues without necessitating full instance recompilations or tenant-wide downtime.

---

## 2. Architectural Foundation

The Modern UI architecture is built around the **Model-View-ViewModel (MVVM)** pattern:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         CLIENT-SIDE (BROWSER)                            │
│                                                                          │
│   VIEW (HTML Template)               VIEW MODEL (TypeScript)             │
│   • <template>                       • PXScreen (Screen Class)           │
│   • <qp-template>, <qp-fieldset>     • PXView (View Class / DAC State)   │
│   • <qp-grid>, <qp-tabbar>           • Decorators (@graphInfo, etc.)     │
│   • Aurelia Data Binding             • client-controls library           │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ JSON over HTTP (REST / Web APIs)
┌────────────────────────────────────┴─────────────────────────────────────┐
│                         SERVER-SIDE (.NET / C#)                          │
│                                                                          │
│   MODEL / BUSINESS LOGIC CONTROLLER (BLC)                                │
│   • PXGraph / PXGraphExtension (Business Logic)                          │
│   • IBqlTable / PXCacheExtension (Data Access Classes - DACs)            │
│   • Workflows & Event Handlers (FieldUpdating, RowSelected, etc.)        │
│   • Business Query Language (BQL / Fluent BQL)                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### Core Architecture Highlights:
1. **Shared Business Logic**: The backend C# graph (`PXGraph`), DACs (`IBqlTable`), BQL queries, and workflows remain identical.
   Both Classic and Modern UI interact with the same underlying graph.
   Backend developers write standard Acumatica C# business logic.
2. **SPA Client**: The frontend is built on **Aurelia**, using Web Components (`qp-*` custom element namespace).
3. **Data Protocol**: All UI data exchanges, validations, and action invocations communicate with web API controllers using standardized JSON payloads.
4. **State Machine (`PXFieldState`)**: The backend continues to be the single source of truth for field metadata (enabled, disabled, hidden, required, allowed values, error states).
   The server pushes these states down into `PXFieldState` objects on the client.

---

## 3. The Two Modern UI Customization Patterns

Modern UI customizations fall into two distinct engineering patterns:

### Pattern A: Customizing Existing Forms (Extensions)
Used when extending out-of-the-box Acumatica screens (e.g., adding custom `Usr*` fields, rearranging sections, injecting tabs, or altering grid configurations).

- **Mechanism**: Non-destructive differential extensions (differential HTML mutation and TypeScript view extension classes).
- **Files Involved**:
  - `FrontendSources\screen\src\development\screens\<Module>\<ScreenID>\extensions\<ScreenID>_<ExtensionName>.html`
  - `FrontendSources\screen\src\development\screens\<Module>\<ScreenID>\extensions\<ScreenID>_<ExtensionName>.ts`

### Pattern B: Creating New Custom Screens from Scratch
Used when creating brand-new business functionality (e.g., new ISV modules like Quality Management `QM101000`, `QM201000`).

- **Mechanism**: Full standalone screen definition implementing a `PXScreen` class, associated `PXView` classes, and a primary `<template>`.
- **Files Involved**:
  - `FrontendSources\screen\src\development\screens\<Module>\<ScreenID>\<ScreenID>.html`
  - `FrontendSources\screen\src\development\screens\<Module>\<ScreenID>\<ScreenID>.ts`
  - Optional `views.ts` for large forms with multiple data views.

---

## 4. Pattern A: Screen Extensions & Layout Mutation (Detailed)

In Classic UI, modifying an ASPX page often involved overwriting large chunks of markup or fragile node diffing.
Modern UI uses **DOM mutation directives** evaluated against the base template using CSS selectors.

### HTML Extension Directives

All HTML extension markup must reside in a root `<template>` tag.
Elements specify where and how they alter the base DOM using directive attributes:

| Directive Attribute | Target Value | Description |
| :--- | :--- | :--- |
| `modify` | CSS Selector (e.g., `#main`, `#tab-PriceCost`) | Modifies attributes and configuration of an existing element. |
| `after` | CSS Selector (e.g., `#fsSummary [name='OrderDate']`) | Inserts the new element immediately after the referenced element. |
| `before` | CSS Selector | Inserts the new element immediately before the referenced element. |
| `append` | CSS Selector | Appends the element as the last child of the target container. |
| `prepend` | CSS Selector | Prepends the element as the first child of the target container. |
| `replace` | CSS Selector | Replaces the target element entirely. |
| `remove` | CSS Selector | Removes the target element from the DOM. |

### HTML Extension Example (Adding Fields & Tabs)

```html
<template>
  <!-- 1. Append custom fields to an existing fieldset -->
  <template modify="#fsItemSettings">
    <field name="UsrInspectionRequired" after="#fsItemSettings [name='ItemClassID']"></field>
    <field name="UsrInspectionPlanID" after="#fsItemSettings [name='UsrInspectionRequired']"></field>
  </template>

  <!-- 2. Add a new tab after an existing tab -->
  <qp-tab
    id="tab-QualityControl"
    caption="Quality Control"
    after="#tab-PriceCost"
    visible.bind="Item.UsrInspectionRequired.value === true">
    
    <qp-grid id="grid-QualityTests" view.bind="InspectionTests"></qp-grid>
  </qp-tab>
</template>
```

> **Critical 2026 R1 Bug Workaround Note**: When applying conditional visibility on tabs or containers, use `visible.bind="..."` instead of `if.bind="..."`. In 2026 R1, `if.bind` can lead to DOM detachment bugs in tab bars where tab header buttons do not reconcile properly.

### TypeScript Extension Pattern

When custom fields (`Usr*`) or custom data views are injected into an existing screen, they must be exposed to the TypeScript layer by extending the corresponding View class:

```typescript
import {
  PXView,
  PXFieldState,
  PXFieldOptions,
  createCollection,
  gridConfig,
  GridPreset,
  controlConfig
} from "client-controls";

// 1. Extend the DAC View bound to the fieldset where Usr* fields reside
export class InventoryItemExtension extends PXView {
  @controlConfig({ commitChanges: true })
  UsrInspectionRequired: PXFieldState<PXFieldOptions.CommitChanges>;

  @controlConfig({ allowEdit: true })
  UsrInspectionPlanID: PXFieldState;
}

// 2. View class for the new grid data view
@gridConfig({
  preset: GridPreset.Details
})
export class QMInspectionPlanTest extends PXView {
  TestCD: PXFieldState<PXFieldOptions.CommitChanges>;
  Description: PXFieldState;
  TargetValue: PXFieldState;
  ToleranceMin: PXFieldState;
  ToleranceMax: PXFieldState;
}

// 3. Screen extension declaring newly added data views
export class IN202500_QMS {
  InspectionTests = createCollection(QMInspectionPlanTest);
}
```

---

## 5. Pattern B: New Custom Screens (Detailed)

Creating a new screen from scratch requires pairing a `<ScreenID>.ts` view model with a `<ScreenID>.html` template.

### TypeScript View Model Implementation

```typescript
import {
  PXScreen,
  PXView,
  PXFieldState,
  PXFieldOptions,
  createSingle,
  createCollection,
  graphInfo,
  viewInfo,
  gridConfig,
  controlConfig,
  GridPreset,
  PXPageLoadBehavior
} from "client-controls";

// Main Screen Class
@graphInfo({
  graphType: "Lab5.QMS.InspectionPlanMaint",
  primaryView: "Plans",
  pageLoadBehavior: PXPageLoadBehavior.GoFirstRecord,
  hideFilesIndicator: false,
  hideNotesIndicator: false
})
export class QM201000 extends PXScreen {
  // Single-record container for Header / Summary area
  @viewInfo({ containerName: "Inspection Plan" })
  Plans = createSingle(QMInspectionPlan);

  // Collection container for Tab / Details Grid
  @viewInfo({ containerName: "Inspection Tests" })
  Tests = createCollection(QMInspectionTest);
}

// Primary View Class (Header DAC)
export class QMInspectionPlan extends PXView {
  PlanCD: PXFieldState<PXFieldOptions.CommitChanges>;
  Description: PXFieldState;
  
  @controlConfig({ commitChanges: true })
  Active: PXFieldState<PXFieldOptions.CommitChanges>;
  
  TotalTests: PXFieldState<PXFieldOptions.Disabled>;
}

// Details View Class (Grid Lines DAC)
@gridConfig({
  preset: GridPreset.Details,
  allowInsert: true,
  allowDelete: true
})
export class QMInspectionTest extends PXView {
  TestCD: PXFieldState<PXFieldOptions.CommitChanges>;
  Description: PXFieldState;
  TargetValue: PXFieldState;
  ToleranceMin: PXFieldState;
  ToleranceMax: PXFieldState;
  IsRequired: PXFieldState;
}
```

### HTML Template Implementation

```html
<template>
  <!-- Summary / Form Area: 7-10-7 Responsive Template -->
  <qp-template id="form-Plans" name="7-10-7" wg-container="Plans_form">
    <qp-fieldset id="fsColumnA-Plans" slot="A" view.bind="Plans">
      <field name="PlanCD"></field>
      <field name="Description"></field>
    </qp-fieldset>

    <qp-fieldset id="fsColumnB-Plans" slot="B" view.bind="Plans">
      <field name="Active"></field>
    </qp-fieldset>

    <qp-fieldset id="fsColumnC-Plans" slot="C" view.bind="Plans" class="highlights-section">
      <field name="TotalTests"></field>
    </qp-fieldset>
  </qp-template>

  <!-- Details Area: Tabs and Grid -->
  <qp-tabbar id="tabsPlan">
    <qp-tab id="tabTests" caption="Tests">
      <qp-grid id="gridTests" view.bind="Tests"></qp-grid>
    </qp-tab>
  </qp-tabbar>
</template>
```

### Key Elements of Modern UI Controls:
- `<field name="...">`: Developers do **not** specify individual control types like `qp-checkbox` or `qp-text-box`.
  The server evaluates the DAC field's attributes (`PXDBString`, `PXDBBool`, `PXSelector`, `PXUIField`) and assigns the appropriate control automatically.
- `<qp-template name="...">`: Predefined responsive layout templates (e.g., `1-1`, `7-10-7`, `1-1-1`).
- `slot="A"`, `slot="B"`: Layout slots defined by the parent `qp-template`.
- `view.bind="..."`: Aurelia binding that connects a container to a property declared via `createSingle` or `createCollection`.

---

## 6. TypeScript Decorator Ecosystem

Acumatica uses TypeScript decorators from `client-controls` to configure client-side behavior without polluting HTML markup:

| Decorator | Scope | Common Options | Purpose |
| :--- | :--- | :--- | :--- |
| `@graphInfo` | Screen Class (`PXScreen`) | `graphType`, `primaryView`, `pageLoadBehavior`, `hideFilesIndicator` | Links frontend screen to backend C# graph. |
| `@viewInfo` | Screen Property | `containerName` | Sets the object container name for workflows and import/export scenarios. |
| `@gridConfig` | View Class (`PXView`) | `preset: GridPreset.Primary / Details`, `allowInsert`, `allowDelete` | Governs grid toolbar, editing behaviors, and display modes. |
| `@controlConfig` | Field (`PXFieldState`) | `allowEdit: true`, `commitChanges: true`, `rows: 3` | Configures input control specifics (selector hyperlink, multiline rows). |
| `@columnConfig` | Field (`PXFieldState`) | `allowNull: false`, `hideViewLink: true`, `width: 150` | Overrides column layout behaviors within grids. |

---

## 7. 2026 R1 Developer Workflow & Tooling

### Local File System Layout
Acumatica instances maintain the Modern UI source tree in the website root:

```
<AcumaticaSiteRoot>
  └── FrontendSources\
      └── screen\
          ├── package.json
          ├── webpack.config.js
          └── src\
              ├── screens\                    <-- Out-of-the-box Acumatica screens
              │   ├── IN\IN202500\...
              │   └── SO\SO301000\...
              └── development\                <-- NEW & CUSTOMIZED SCREENS (2026 R1)
                  └── screens\
                      ├── IN\IN202500\extensions\
                      │   ├── IN202500_PhoneRepairShop.html
                      │   └── IN202500_PhoneRepairShop.ts
                      └── QM\QM201000\
                          ├── QM201000.html
                          └── QM201000.ts
```

### Build & Compilation Commands
All Modern UI compilation is driven by Webpack through npm scripts in `FrontendSources\screen`:

1. **Install Frontend Dependencies**:
   ```powershell
   cd FrontendSources
   npm run getmodules
   ```
2. **Compile Development Screens (Targeted)**:
   ```powershell
   cd FrontendSources\screen
   npm run build-dev --- --env customFolder=development screenIds=QM201000
   ```
3. **Compile by Functional Module**:
   ```powershell
   npm run build-dev --- --env customFolder=development modules="QM,IN"
   ```
4. **Active Watch Mode (Hot Rebuild on Save)**:
   ```powershell
   npm run watch --- --env customFolder=development screenIds=QM201000
   ```
*(Always provide `screenIds` or `modules` to avoid performance degradation.)*

### 2026 R1 Synchronization Innovation
In 2025 R2, developers had to manually move files from `development\` into the customization project.
In **2026 R1**:
- You build directly against `FrontendSources\screen\src\development\`.
- Files created in the `development` folder automatically synchronize with the Customization Project Editor.
- When exporting a customization package, the engine includes the synchronized Modern UI files.

---

## 8. Customization Project Packaging & Publishing

### Modern UI Project Items in `project.xml`
In the customization package archive (`.zip`), Modern UI files are stored and declared in `project.xml`:

```xml
<Customization level="0" description="Lab5.QMS Customization" product-version="22.200.001">
  <!-- Screen Registration -->
  <Page Type="Page" ScreenID="QM201000" Title="Inspection Plan" />

  <!-- Modern UI Source Files published to instance directory -->
  <File AppRelativePath="FrontendSources\screen\src\screens\QM\QM201000\QM201000.html" />
  <File AppRelativePath="FrontendSources\screen\src\screens\QM\QM201000\QM201000.ts" />

  <!-- Customization Assembly containing backend Graphs and DACs -->
  <File AppRelativePath="Bin\Lab5.QMS.dll" />
</Customization>
```

### Publication Lifecycle:
1. **Validation**: The customization engine checks C# syntax, graph extensions, and Modern UI TypeScript contracts.
2. **File Extraction**: Modern UI files are extracted into `FrontendSources`.
3. **Automated Webpack Build**: The publisher invokes `npm run build` internally.
   Output JavaScript bundles are placed in `Scripts/Screens/`.
4. **Database & Schema Updates**: Bound custom fields, custom tables, and site map entries are executed.
5. **Logs**: Detailed TypeScript and Webpack build logs are emitted to `App_Data\logs`.

### Web.config Configuration for Modern UI Builds
Key parameters in `web.config` control frontend compilation:
```xml
<appSettings>
  <!-- Node.js path (if not using default embedded Node) -->
  <add key="NodeJs:NodeTempPath" value="C:\Acumatica\NodeTemp" />
  <!-- Compile in dev mode for browser source-map debugging -->
  <add key="NodeJs:DevBuild" value="true" />
  <!-- Incremental build (false) or full build (true) -->
  <add key="NodeJs:CompileAllScreens" value="false" />
  <!-- Production npm cache directory -->
  <add key="NodeJs:NpmCachePath" value="C:\instances\site\App_Data\npm-cache" />
</appSettings>
```

---

## 9. Common Pitfalls & Migration Insights

### 1. Classic `Usr*` Fields Do Not Auto-Migrate
- **Symptom**: After converting a screen to Modern UI in 2026 R1, custom DAC extension fields (`UsrXxx`) that worked fine in Classic UI disappear.
- **Cause**: The Classic-to-Modern UI converter does not carry over DAC extension fields into the Modern UI layout.
  Screen Configuration (`Tools > Screen Configuration`) only exposes User-Defined Fields (UDF attributes), not C# DAC extension fields.
- **Remedy**: Each DAC extension field must be explicitly added using the **Modern UI Editor** (`AU201080`):
  1. Open Customization Project Editor $\rightarrow$ `Screens` $\rightarrow$ Select Screen $\rightarrow$ `Modern UI Editor`.
  2. Click **Add Field** $\rightarrow$ select Data View $\rightarrow$ select DAC $\rightarrow$ select `Usr*` fields.
  3. Click **Save to Extension** $\rightarrow$ place field in HTML tab $\rightarrow$ **Save** & **Publish**.

### 2. Multi-Tenant Customization Rules
- Modern UI files (`.html`, `.ts`, and compiled Webpack bundles in `Scripts/Screens`) are stored in the website filesystem and therefore affect **all tenants** on the instance.
- Form personalizations (Screen Configuration) and metadata (Access Rights, Generic Inquiries) remain **tenant-specific**.

### 3. Screen ID Class Naming
- In TypeScript, the screen class name **must strictly match the 8-character Screen ID** (e.g., `export class QM201000 extends PXScreen`).
  Failure to match prevents the Aurelia router from resolving the view model.

### 4. Graph Uniqueness
- In Modern UI, each screen must have its own unique graph type.
  Sharing the same graph type across multiple screens without subclassing causes router state collision.

---

## 10. Architectural Comparison Matrix

| Feature | Classic UI (ASPX) | Modern UI (2026 R1) |
| :--- | :--- | :--- |
| **Frontend Framework** | ASP.NET Web Forms (Server Controls) | Aurelia SPA + Web Components (`qp-*`) |
| **Client Language** | ASPX markup + inline JavaScript | TypeScript + HTML5 Templates |
| **Component Model** | `PXFormView`, `PXGrid`, `PXTab` | `<qp-template>`, `<qp-fieldset>`, `<qp-grid>`, `<qp-tab>` |
| **Field Definition** | `<px:PXTextEdit DataField="Field">` | `<field name="Field"></field>` (Auto-typed by server) |
| **Layout System** | `PXLayoutRule` (Row/Column rules) | Responsive Grid Templates (`7-10-7`, `1-1`, etc.) |
| **Screen Extension** | Modifying `.aspx` or Page XML node diff | Targeted HTML mutation (`modify`, `after`, `before`) |
| **Logic Extension** | Server-side Graph Extension only | C# Graph Extension + TypeScript View Extension |
| **Client-Side Configuration** | ASPX control properties (`AllowEdit="True"`) | TypeScript Decorators (`@controlConfig`, `@gridConfig`) |
| **Development Directory** | `Pages/<Module>/<Screen>.aspx` | `FrontendSources/screen/src/development/screens/` |
| **Build Mechanism** | JIT ASP.NET compilation / Roslyn | Webpack bundle build via Node.js / npm |
| **Future Support** | **Deprecated in 2026 R2** | **Standard / Future Platform Architecture** |

---

## 11. Recommendations for Projects & ISVs in 2026 R1

1. **Stop Building ASPX Pages Immediately**: All new custom forms must be authored with TypeScript (`.ts`) and Modern UI HTML (`.html`).
2. **Audit Existing `Usr*` Extensions**: Inspect all customizations deployed to 2026 R1.
   Ensure DAC extension fields on standard forms have corresponding Modern UI TypeScript extensions and HTML mutation templates.
3. **Adopt the `development\` Folder Workflow**: Utilize `FrontendSources\screen\src\development\screens\` for local screen development and take advantage of 2026 R1 direct compilation and automatic package synchronization.
4. **Validate Against 2026 R2 Deprecation**: Test complete regression suites with Classic UI disabled to ensure that smart panels, side panels, and custom actions operate seamlessly in the pure Modern UI environment.
