using PX.Data;

namespace Lab5.QMS
{
    public static class QMSInspectionOrderStatus
    {
        public const string Open = "O";
        public const string Completed = "C";
        public const string Cancelled = "X";

        public class ListAttribute : PXStringListAttribute
        {
            public ListAttribute()
                : base(
                    new[] { Open, Completed, Cancelled },
                    new[] { "Open", "Completed", "Cancelled" })
            {
            }
        }

        public class open : PX.Data.BQL.BqlString.Constant<open>
        {
            public open() : base(Open) { }
        }

        public class completed : PX.Data.BQL.BqlString.Constant<completed>
        {
            public completed() : base(Completed) { }
        }

        public class cancelled : PX.Data.BQL.BqlString.Constant<cancelled>
        {
            public cancelled() : base(Cancelled) { }
        }
    }

    public static class QMSOverallEvaluation
    {
        public const string Pending = "P";
        public const string Pass = "V";
        public const string Fail = "F";

        public class ListAttribute : PXStringListAttribute
        {
            public ListAttribute()
                : base(
                    new[] { Pending, Pass, Fail },
                    new[] { "Pending", "Pass", "Fail" })
            {
            }
        }
    }

    public static class QMSLineEvaluation
    {
        public const string Pass = "P";
        public const string Fail = "F";
        public const string Skipped = "S";

        public class ListAttribute : PXStringListAttribute
        {
            public ListAttribute()
                : base(
                    new[] { Pass, Fail, Skipped },
                    new[] { "Pass", "Fail", "Skipped" })
            {
            }
        }
    }
}
