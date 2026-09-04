using System;
using System.Collections.Generic;

namespace Lab5.QMS
{
    /// <summary>V2/V3/I.files: attach CoA PDF + parsed JSON via /files on InspectionOrder NoteID.</summary>
    public static class QMSCoAFileRules
    {
        public const string PdfExtension = ".pdf";
        public const string JsonExtension = ".json";
        public const string ExpandFiles = "files";

        public static string FilesPath(string inspectionOrderNbr, string fileName)
        {
            return "/entity/" + QMS.EndpointName + "/" + QMS.EndpointVersion
                + "/InspectionOrder/" + inspectionOrderNbr + "/files/" + fileName;
        }

        public static bool IsCoaPdf(string fileName)
        {
            return HasExtension(fileName, PdfExtension);
        }

        public static bool IsParsedJson(string fileName)
        {
            return HasExtension(fileName, JsonExtension);
        }

        public static bool HasSystemOfRecord(IEnumerable<string> fileNames)
        {
            if (fileNames == null)
            {
                return false;
            }
            bool pdf = false;
            bool json = false;
            foreach (string name in fileNames)
            {
                if (IsCoaPdf(name))
                {
                    pdf = true;
                }
                if (IsParsedJson(name))
                {
                    json = true;
                }
            }
            return pdf && json;
        }

        static bool HasExtension(string fileName, string extension)
        {
            if (string.IsNullOrEmpty(fileName) || string.IsNullOrEmpty(extension))
            {
                return false;
            }
            return fileName.EndsWith(extension, StringComparison.OrdinalIgnoreCase);
        }
    }
}
