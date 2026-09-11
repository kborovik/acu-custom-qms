using PX.Data;

namespace Lab5.QMS
{
    public static class QMSInspectionPlanStatus
    {
        public const string Active = "A";
        public const string Hold = "H";
        public const string Inactive = "I";

        public class ListAttribute : PXStringListAttribute
        {
            public ListAttribute()
                : base(
                    new[] { Active, Hold, Inactive },
                    new[] { "Active", "Hold", "Inactive" })
            {
            }
        }

        public class active : PX.Data.BQL.BqlString.Constant<active>
        {
            public active() : base(Active) { }
        }

        public class hold : PX.Data.BQL.BqlString.Constant<hold>
        {
            public hold() : base(Hold) { }
        }

        public class inactive : PX.Data.BQL.BqlString.Constant<inactive>
        {
            public inactive() : base(Inactive) { }
        }
    }
}
