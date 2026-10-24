using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: AssemblyTitle("ImaginePro")]
[assembly: AssemblyDescription("One-click ImaginePro local editor launcher")]
[assembly: AssemblyProduct("ImaginePro")]
[assembly: AssemblyVersion("1.0.0.0")]

internal sealed class LaunchFailure : Exception {
    internal bool SignIn;
    internal LaunchFailure(string message, bool signIn = false) : base(message) { SignIn = signIn; }
}

internal static class Studio {
    internal const string Url = "http://127.0.0.1:8765";
    internal static readonly string Root = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
    internal static readonly string Storage = Path.GetFullPath(Environment.GetEnvironmentVariable("VIDEO_EDITOR_STORAGE") ?? Path.Combine(Root, "storage"));
    internal static readonly string Logs = Path.Combine(Storage, "logs");
    internal static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    internal static readonly string InstallId = Hash(Root.ToLowerInvariant());

    internal static string Hash(string input) {
        using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(input))).Replace("-", "").ToLowerInvariant().Substring(0,20);
    }
    internal static void Log(string message) {
        Directory.CreateDirectory(Logs);
        File.AppendAllText(Path.Combine(Logs, "launcher.log"), DateTime.UtcNow.ToString("o") + " " + message + Environment.NewLine);
    }
    internal static void Result(bool success, bool started, bool opened, string message) {
        string directory = Path.Combine(Storage, "desktop"); Directory.CreateDirectory(directory);
        File.WriteAllText(Path.Combine(directory, "last-launch.json"), Json.Serialize(new {
            success = success, started_server = started, opened_browser = opened,
            codex_connected = success, installation_id = InstallId, url = Url,
            message = message, checked_at = DateTime.UtcNow.ToString("o")
        }), Encoding.UTF8);
    }
    internal static Dictionary<string,object> Read(string route, int seconds) {
        using (var handler = new HttpClientHandler { UseProxy = false, AllowAutoRedirect = false })
        using (var client = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(seconds) }) {
            var response = client.GetAsync(Url + route).GetAwaiter().GetResult();
            if (response.StatusCode != HttpStatusCode.OK) return null;
            string body = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
            if (body.Length > 100000) return null;
            return Json.Deserialize<Dictionary<string,object>>(body);
        }
    }
    internal static Dictionary<string,object> Health() {
        try { return Read("/api/health", 2); } catch { return null; }
    }
    internal static bool IsOurs(Dictionary<string,object> data) {
        return data != null && data.ContainsKey("application") && Convert.ToString(data["application"]) == "ImaginePro"
            && data.ContainsKey("installation_id") && Convert.ToString(data["installation_id"]) == InstallId;
    }
    internal static bool PortInUse() {
        try { using (var socket = new TcpClient()) { var connection = socket.ConnectAsync("127.0.0.1",8765); return connection.Wait(500) && socket.Connected; } }
        catch { return false; }
    }
    internal static void Required(string relative, string explanation) {
        if (!File.Exists(Path.Combine(Root,relative))) throw new LaunchFailure(explanation);
    }
    internal static void OpenBrowser() { Process.Start(new ProcessStartInfo(Url) { UseShellExecute = true }); }
    internal static void OpenLogs() { Directory.CreateDirectory(Logs); Process.Start(new ProcessStartInfo(Logs) { UseShellExecute = true }); }

    internal static void Launch(bool openBrowser, bool allowStart, Action<string> update) {
        bool started = false, opened = false;
        try {
            Required("backend/main.py", "Keep ImaginePro.exe in its application folder. Use the desktop shortcut to open it.");
            Required("frontend/out/index.html", "The editor build is missing. Run scripts/start.ps1 -Build from the application folder.");
            // Serialize startup across double-clicks. An existing matching server is always reused.
            using (var mutex = new Mutex(false, "Local\\ImaginePro.Launcher." + InstallId)) {
                bool owns = false;
                try {
                    update("Connecting to your studio…");
                    try { owns = mutex.WaitOne(TimeSpan.FromSeconds(90)); } catch (AbandonedMutexException) { owns = true; }
                    if (!owns) throw new LaunchFailure("ImaginePro is still starting. Try again in a moment.");
                    var health = Health();
                    if (!IsOurs(health)) {
                        if (PortInUse()) {
                            // A second launcher may reach the port during server startup.
                            for (int i=0; i<8 && !IsOurs(health); i++) { Thread.Sleep(500); health=Health(); }
                            if (!IsOurs(health)) throw new LaunchFailure("Port 8765 is in use by a different service or application folder. Close that service, then reopen ImaginePro. Your projects have not changed.");
                        } else {
                            if (!allowStart) throw new LaunchFailure("ImaginePro is not running.");
                            Required(".venv/Scripts/pythonw.exe", "ImaginePro's Python environment is missing. Restore the application folder or run scripts/start.ps1 -Install.");
                            Required("desktop/server.pyw", "The desktop server entry point is missing. Restore the application folder.");
                            Required("backend/framecraft/node_modules/puppeteer-core/package.json", "Animation dependencies are missing. Run scripts/start.ps1 -Install.");
                            update("Starting the editor and media engine…");
                            var info = new ProcessStartInfo(Path.Combine(Root,".venv/Scripts/pythonw.exe"), "-X utf8 \"" + Path.Combine(Root,"desktop/server.pyw") + "\"");
                            info.WorkingDirectory=Root; info.UseShellExecute=false; info.CreateNoWindow=true; info.WindowStyle=ProcessWindowStyle.Hidden;
                            info.EnvironmentVariables["PYTHONUNBUFFERED"]="1";
                            // Do not inherit a developer's import path from a terminal or parent app.
                            info.EnvironmentVariables.Remove("PYTHONPATH");
                            using (var server = Process.Start(info)) {
                                started=true;
                                var limit=DateTime.UtcNow.AddSeconds(75);
                                while (DateTime.UtcNow < limit) {
                                    health=Health(); if (IsOurs(health)) break;
                                    if (server.HasExited) throw new LaunchFailure("The editor could not start. Open logs for the error, then try again.");
                                    Thread.Sleep(250);
                                }
                            }
                            if (!IsOurs(health)) throw new LaunchFailure("The editor is taking too long to start. Open logs or try again; your files are preserved.");
                        }
                    }
                    update("Checking rendering tools…");
                    object toolsObject;
                    if (!health.TryGetValue("tools",out toolsObject)) throw new LaunchFailure("The editor health check is incomplete. Open logs for details.");
                    var tools = toolsObject as Dictionary<string,object>;
                    foreach (string tool in new [] { "ffmpeg","ffprobe","node","codex","faster_whisper","animation_browser","animation_engine","frontend" }) {
                        if (tools == null || !tools.ContainsKey(tool) || !Convert.ToBoolean(tools[tool]))
                            throw new LaunchFailure("A required component is unavailable: " + tool + ". Open logs or run scripts/start.ps1 -Install.");
                    }
                    update("Connecting your Codex account…");
                    var account=Read("/api/runtime",22);
                    if (account == null || !account.ContainsKey("authenticated_with_chatgpt") || !Convert.ToBoolean(account["authenticated_with_chatgpt"]))
                        throw new LaunchFailure("Codex needs its normal ChatGPT sign-in. Choose Sign in to Codex, finish signing in, then click Try again.",true);
                    if (openBrowser) { update("Opening ImaginePro…"); OpenBrowser(); opened=true; }
                    Result(true,started,opened,"Editor ready; Codex account connected");
                    Log(started ? "Started editor; Codex connected." : "Reused editor; Codex connected.");
                } finally { if (owns) mutex.ReleaseMutex(); }
            }
        } catch (Exception error) {
            string message = error is LaunchFailure ? error.Message : "ImaginePro could not finish starting. Open logs, then try again.";
            Result(false,started,opened,message);
            Log(error is LaunchFailure ? message : error.GetType().Name + ": startup failed");
            if (error is LaunchFailure) throw;
            throw new LaunchFailure(message);
        }
    }

    internal static void SignIn() {
        string local=Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string root=Path.Combine(local,"OpenAI/Codex/bin");
        string exe=Directory.Exists(root) ? Directory.GetFiles(root,"codex.exe",SearchOption.AllDirectories).OrderByDescending(File.GetLastWriteTimeUtc).FirstOrDefault() : null;
        if (exe==null) foreach (string folder in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(Path.PathSeparator)) {
            try { string path=Path.Combine(folder,"codex.exe"); if(File.Exists(path)){exe=path;break;} } catch { }
        }
        if (exe==null) { MessageBox.Show("Install the supported Codex CLI, then reopen ImaginePro.","ImaginePro"); return; }
        // A visible console is intentional only for this explicit interactive sign-in.
        Process.Start(new ProcessStartInfo(exe,"login") { UseShellExecute=true, WorkingDirectory=Root });
    }
}

internal sealed class Launcher : Form {
    readonly Label status = new Label();
    readonly ProgressBar progress = new ProgressBar();
    readonly Button retry = new Button(), logs = new Button(), signIn = new Button();
    bool busy;
    internal Launcher() {
        Text="ImaginePro"; ClientSize=new Size(520,260); FormBorderStyle=FormBorderStyle.FixedSingle;
        MaximizeBox=false; StartPosition=FormStartPosition.CenterScreen; BackColor=Color.FromArgb(13,32,40);
        ForeColor=Color.FromArgb(219,242,236); Font=new Font("Segoe UI",10);
        Icon=Icon.ExtractAssociatedIcon(Assembly.GetExecutingAssembly().Location);
        var title=new Label { Text="ImaginePro", Location=new Point(28,22),Size=new Size(450,40),Font=new Font("Segoe UI",24,FontStyle.Bold),ForeColor=Color.FromArgb(176,248,217) };
        var subtitle=new Label { Text="Your creative studio, ready in a moment.",Location=new Point(31,70),Size=new Size(460,25),ForeColor=Color.FromArgb(151,181,190) };
        status.Location=new Point(31,112);status.Size=new Size(456,69);status.Text="Starting…";
        progress.Location=new Point(31,187);progress.Size=new Size(456,5);progress.Style=ProgressBarStyle.Marquee;
        var footer=new Label {Text="Projects and media stay in your existing workspace.",Location=new Point(31,215),Size=new Size(460,25),ForeColor=Color.FromArgb(151,181,190),Font=new Font("Segoe UI",9)};
        Configure(retry,"Try again",31); Configure(logs,"Open logs",161); Configure(signIn,"Sign in to Codex",291);
        retry.Click+=async delegate { await Start(); };logs.Click+=delegate { Studio.OpenLogs(); };signIn.Click+=delegate { Studio.SignIn(); };
        Controls.AddRange(new Control[]{title,subtitle,status,progress,footer,retry,logs,signIn});
        Shown+=async delegate { await Start(); };
    }
    void Configure(Button button,string text,int x) {
        button.Text=text;button.Location=new Point(x,184);button.Size=new Size(122,29);button.FlatStyle=FlatStyle.Flat;
        button.ForeColor=Color.FromArgb(176,248,217);button.Visible=false;
    }
    async Task Start() {
        if(busy)return;busy=true;retry.Visible=logs.Visible=signIn.Visible=false;progress.Visible=true;
        try {
            await Task.Run(delegate { Studio.Launch(true,true,delegate(string message){if(!IsDisposed && IsHandleCreated)BeginInvoke((Action)delegate {status.Text=message;});}); });
            Close();
        } catch(LaunchFailure error) { status.Text=error.Message;progress.Visible=false;retry.Visible=logs.Visible=true;signIn.Visible=error.SignIn; }
        finally {busy=false;}
    }
}

internal static class Program {
    [STAThread] static int Main(string[] args) {
        if(args.Contains("--no-browser") || args.Contains("--check")) {
            try { Studio.Launch(false,!args.Contains("--check"),delegate(string message){});return 0; }
            catch { return 1; }
        }
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new Launcher());return 0;
    }
}
