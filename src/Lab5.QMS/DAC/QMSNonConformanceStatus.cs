using PX.Data;

namespace Lab5.QMS
{
    public static class QMSNonConformanceStatus
    {
        public const string Open = "O";
        public const string InInvestigation = "I";
        public const string Closed = "C";
        public const string Void = "V";

        public class ListAttribute : PXStringListAttribute
        {
            public ListAttribute()
                : base(
                    new[] { Open, InInvestigation, Closed, Void },
                    new[] { "Open", "In Investigation", "Closed", "Void" })
            {
            }
        }

        public class open : PX.Data.BQL.BqlString.Constant<open>
        {
            public open() : base(Open) { }
        }

        public class inInvestigation : PX.Data.BQL.BqlString.Constant<inInvestigation>
        {
            public inInvestigation() : base(InInvestigation) { }
        }

        public class closed : PX.Data.BQL.BqlString.Constant<closed>
        {
            public closed() : base(Closed) { }
        }

        public class voided : PX.Data.BQL.BqlString.Constant<voided>
        {
            public voided() : base(Void) { }
        }
    }

    public static class QMSSeverity
    {
        public const string Critical = "C";
        public const string Major = "M";
        public const string Minor = "m";

        public class ListAttribute : PXStringListAttribute
        {
            public ListAttribute()
                : base(
                    new[] { Critical, Major, Minor },
                    new[] { "Critical", "Major", "Minor" })
            {
            }
        }

        public class critical : PX.Data.BQL.BqlString.Constant<critical>
        {
            public critical() : base(Critical) { }
        }
    }

    public static class QMSInventoryHoldStatus
    {
        public const string Quarantine = "Quarantine";
        public const string Rejected = "Rejected";

        public class ListAttribute : PXStringListAttribute
        {
            public ListAttribute()
                : base(
                    new[] { Quarantine, Rejected },
                    new[] { "Quarantine", "Rejected" })
            {
            }
        }
    }
}
