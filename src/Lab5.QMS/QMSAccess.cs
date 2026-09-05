using System.Collections.Generic;
using PX.Data;

namespace Lab5.QMS
{
    /// <summary>26.x PXAccess wrappers. GetUserRoles is gone; GetRoles returns PXRoleList.</summary>
    public static class QMSAccess
    {
        public static IEnumerable<string> CurrentUserRoles()
        {
            PXRoleList list = PXAccess.GetRoles(PXAccess.GetUserName());
            if (list == null)
            {
                yield break;
            }
            if (list.Common != null)
            {
                foreach (string role in list.Common)
                {
                    yield return role;
                }
            }
            if (list.Prioritized != null)
            {
                foreach (string role in list.Prioritized)
                {
                    yield return role;
                }
            }
        }

        public static string CurrentUserName()
        {
            return PXAccess.GetUserName();
        }
    }
}
