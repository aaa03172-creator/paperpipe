using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
using Microsoft.Web.WebView2.WinForms;

namespace LatticeNativeLauncher;

internal static class Program
{
    private static readonly string _rootDir = AppContext.BaseDirectory;

    [STAThread]
    private static void Main()
    {
        Environment.SetEnvironmentVariable("PAPERPIPE_SUBMISSION_DEMO_BUNDLE", "1");
        Environment.SetEnvironmentVariable("PAPERPIPE_CLOUD_ADAPTER", "mock");
        Environment.SetEnvironmentVariable("PAPERPIPE_CLOUD_METADATA_STORE", "memory");
        Environment.SetEnvironmentVariable("PAPERPIPE_SUBMISSION_DEMO_BUNDLE_DIR", Path.Combine(_rootDir, "submission_demo"));
        var runtimePath = Path.Combine(_rootDir, "LatticeRuntime.exe");
        if (File.Exists(runtimePath))
        {
            Process.Start(new ProcessStartInfo(runtimePath, "start --host 127.0.0.1 --port 8046") { UseShellExecute = false });
        }
        ApplicationConfiguration.Initialize();
        var form = new Form { Text = "Lattice", Width = 1280, Height = 820 };
        var browser = new WebView2 { Dock = DockStyle.Fill, Source = new Uri("http://127.0.0.1:8046/ui/papers/cloudpdf_lab_001_fe476330a3bd?source=cloud") };
        form.Controls.Add(browser);
        Application.Run(form);
    }
}
