using System;
using System.Collections.Generic;
using PX.Data;
using PX.SM;

namespace Lab5.QMS
{
    /// <summary>26.x PXAccess wrappers. GetUserRoles is gone; GetRoles returns PXRoleList.</summary>
    public static class QMSAccess
    {
        public static IEnumerable<string> CurrentUserRoles()
        {
            HashSet<string> seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            PXRoleList list = PXAccess.GetRoles(PXAccess.GetUserName());
            if (list != null)
            {
                if (list.Common != null)
                {
                    foreach (string role in list.Common)
                    {
                        if (!string.IsNullOrEmpty(role) && seen.Add(role))
                        {
                            yield return role;
                        }
                    }
                }
                if (list.Prioritized != null)
                {
                    foreach (string role in list.Prioritized)
                    {
                        if (!string.IsNullOrEmpty(role) && seen.Add(role))
                        {
                            yield return role;
                        }
                    }
                }
            }
            PXGraph graph = PXGraph.CreateInstance<PXGraph>();
            foreach (UsersInRoles row in PXSelect<UsersInRoles,
                Where<UsersInRoles.username, Equal<Required<UsersInRoles.username>>>>
                .Select(graph, PXAccess.GetUserName()))
            {
                if (!string.IsNullOrEmpty(row.Rolename) && seen.Add(row.Rolename))
                {
                    yield return row.Rolename;
                }
            }
        }

        public static string CurrentUserName()
        {
            return PXAccess.GetUserName();
        }
    }
}
