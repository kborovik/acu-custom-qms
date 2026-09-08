using System;
using PX.Data;
using PX.Objects.IN;

namespace Lab5.QMS
{
    /// <summary>V15 allocate/issue gate: Kit Assembly + IN Issue refuse QC Hold and Quarantine.</summary>
    public static class QMSLotIssueGate
    {
        public static string ReadLotStatus(PXGraph graph, int? inventoryID, string lotSerialNbr)
        {
            if (graph == null || inventoryID == null || !QMSReceiptReleaseRules.HasLot(lotSerialNbr))
            {
                return null;
            }
            INLotSerialStatus lot = PXSelect<INLotSerialStatus,
                Where<INLotSerialStatus.inventoryID, Equal<Required<INLotSerialStatus.inventoryID>>,
                    And<INLotSerialStatus.lotSerialNbr, Equal<Required<INLotSerialStatus.lotSerialNbr>>>>>
                .Select(graph, inventoryID, lotSerialNbr);
            if (lot != null)
            {
                INLotSerialStatusExt ext = lot.GetExtension<INLotSerialStatusExt>();
                if (ext != null && !string.IsNullOrWhiteSpace(ext.UsrQMSLotStatus))
                {
                    return ext.UsrQMSLotStatus;
                }
            }
            foreach (INLotSerialStatusByCostCenter row in PXSelect<INLotSerialStatusByCostCenter,
                Where<INLotSerialStatusByCostCenter.inventoryID, Equal<Required<INLotSerialStatusByCostCenter.inventoryID>>,
                    And<INLotSerialStatusByCostCenter.lotSerialNbr, Equal<Required<INLotSerialStatusByCostCenter.lotSerialNbr>>>>>
                .Select(graph, inventoryID, lotSerialNbr))
            {
                INLotSerialStatusByCostCenterExt ext = row.GetExtension<INLotSerialStatusByCostCenterExt>();
                if (ext != null && !string.IsNullOrWhiteSpace(ext.UsrQMSLotStatus))
                {
                    return ext.UsrQMSLotStatus;
                }
            }
            return null;
        }

        public static void WriteLotStatus(
            PXGraph graph, int? inventoryID, string lotSerialNbr, string lotStatus)
        {
            if (graph == null || inventoryID == null || !QMSReceiptReleaseRules.HasLot(lotSerialNbr))
            {
                return;
            }
            foreach (INLotSerialStatus lot in PXSelect<INLotSerialStatus,
                Where<INLotSerialStatus.inventoryID, Equal<Required<INLotSerialStatus.inventoryID>>,
                    And<INLotSerialStatus.lotSerialNbr, Equal<Required<INLotSerialStatus.lotSerialNbr>>>>>
                .Select(graph, inventoryID, lotSerialNbr))
            {
                INLotSerialStatusExt ext = lot.GetExtension<INLotSerialStatusExt>();
                if (ext != null)
                {
                    ext.UsrQMSLotStatus = lotStatus;
                }
                graph.Caches[typeof(INLotSerialStatus)].Update(lot);
            }
            foreach (INLotSerialStatusByCostCenter lot in PXSelect<INLotSerialStatusByCostCenter,
                Where<INLotSerialStatusByCostCenter.inventoryID, Equal<Required<INLotSerialStatusByCostCenter.inventoryID>>,
                    And<INLotSerialStatusByCostCenter.lotSerialNbr, Equal<Required<INLotSerialStatusByCostCenter.lotSerialNbr>>>>>
                .Select(graph, inventoryID, lotSerialNbr))
            {
                INLotSerialStatusByCostCenterExt ext = lot.GetExtension<INLotSerialStatusByCostCenterExt>();
                if (ext != null)
                {
                    ext.UsrQMSLotStatus = lotStatus;
                }
                graph.Caches[typeof(INLotSerialStatusByCostCenter)].Update(lot);
            }
            PXDatabase.Update<INLotSerialStatusByCostCenter>(
                new PXDataFieldAssign("UsrQMSLotStatus", PXDbType.NVarChar, 10, lotStatus),
                new PXDataFieldRestrict("InventoryID", PXDbType.Int, 4, inventoryID, PXComp.EQ),
                new PXDataFieldRestrict("LotSerialNbr", PXDbType.NVarChar, 100, lotSerialNbr, PXComp.EQ));
        }

        public static void ThrowIfNotIssuable(PXGraph graph, int? inventoryID, string lotSerialNbr)
        {
            ThrowIfNotIssuable(graph, inventoryID, lotSerialNbr, false);
        }

        public static void ThrowIfNotIssuable(
            PXGraph graph,
            int? inventoryID,
            string lotSerialNbr,
            bool fieldException)
        {
            if (inventoryID == null || !QMSReceiptReleaseRules.HasLot(lotSerialNbr))
            {
                return;
            }
            string status = ReadLotStatus(graph, inventoryID, lotSerialNbr);
            if (QMSLotDecisionRules.CanIssue(status))
            {
                return;
            }
            string message = QMSLotDecisionRules.RefuseIssueMessage(lotSerialNbr, status);
            if (fieldException)
            {
                throw new PXSetPropertyException(message);
            }
            throw new PXException(message);
        }

        public static void AssertCacheLots(PXGraph graph, Type dacType)
        {
            if (graph == null || dacType == null)
            {
                return;
            }
            PXCache cache = graph.Caches[dacType];
            foreach (object row in cache.Cached)
            {
                PXEntryStatus entry = cache.GetStatus(row);
                if (entry == PXEntryStatus.Deleted || entry == PXEntryStatus.InsertedDeleted)
                {
                    continue;
                }
                ThrowIfNotIssuable(
                    graph,
                    CacheInt(cache, row, "InventoryID"),
                    cache.GetValue(row, "LotSerialNbr") as string);
            }
        }

        public static void AssertKitLots(PXGraph graph, string docType, string refNbr)
        {
            AssertCacheLots(graph, typeof(INComponentTran));
            AssertCacheLots(graph, typeof(INComponentTranSplit));
            if (string.IsNullOrEmpty(docType) || string.IsNullOrEmpty(refNbr))
            {
                return;
            }
            foreach (INComponentTran line in PXSelect<INComponentTran,
                Where<INComponentTran.docType, Equal<Required<INComponentTran.docType>>,
                    And<INComponentTran.refNbr, Equal<Required<INComponentTran.refNbr>>>>>
                .Select(graph, docType, refNbr))
            {
                ThrowIfNotIssuable(graph, line.InventoryID, line.LotSerialNbr);
            }
            foreach (INComponentTranSplit split in PXSelect<INComponentTranSplit,
                Where<INComponentTranSplit.docType, Equal<Required<INComponentTranSplit.docType>>,
                    And<INComponentTranSplit.refNbr, Equal<Required<INComponentTranSplit.refNbr>>>>>
                .Select(graph, docType, refNbr))
            {
                ThrowIfNotIssuable(graph, split.InventoryID, split.LotSerialNbr);
            }
        }

        public static void AssertIssueLots(PXGraph graph, string docType, string refNbr)
        {
            AssertCacheLots(graph, typeof(INTran));
            AssertCacheLots(graph, typeof(INTranSplit));
            if (string.IsNullOrEmpty(docType) || string.IsNullOrEmpty(refNbr))
            {
                return;
            }
            foreach (INTran line in PXSelect<INTran,
                Where<INTran.docType, Equal<Required<INTran.docType>>,
                    And<INTran.refNbr, Equal<Required<INTran.refNbr>>>>>
                .Select(graph, docType, refNbr))
            {
                ThrowIfNotIssuable(graph, line.InventoryID, line.LotSerialNbr);
            }
            foreach (INTranSplit split in PXSelect<INTranSplit,
                Where<INTranSplit.docType, Equal<Required<INTranSplit.docType>>,
                    And<INTranSplit.refNbr, Equal<Required<INTranSplit.refNbr>>>>>
                .Select(graph, docType, refNbr))
            {
                ThrowIfNotIssuable(graph, split.InventoryID, split.LotSerialNbr);
            }
        }

        static int? CacheInt(PXCache cache, object row, string field)
        {
            object raw = cache.GetValue(row, field);
            if (raw is int value)
            {
                return value;
            }
            return raw as int?;
        }
    }
}
