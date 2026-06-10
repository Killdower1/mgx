using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Windows.Forms;

public class DifotoinDashboardLauncher
{
    private const string DefaultEmail = "octadimas@gmail.com";
    private const string DashboardUrl = "http://localhost:8501";

    [STAThread]
    public static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);

        string exeDir = AppDomain.CurrentDomain.BaseDirectory;
        string appDir = Path.Combine(exeDir, "streamlit_template");
        if (!Directory.Exists(appDir))
        {
            MessageBox.Show(
                "Folder streamlit_template tidak ditemukan.\n\nTaruh file EXE ini di root project mgx.",
                "Difotoin Dashboard",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return;
        }

        LoginInput login = PromptLogin();
        if (login == null)
        {
            return;
        }

        string pythonExe = ResolvePython(appDir);
        try
        {
            using (StatusForm statusForm = new StatusForm(pythonExe, appDir, login))
            {
                Application.Run(statusForm);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                "Gagal menjalankan dashboard:\n\n" + ex.Message,
                "Difotoin Dashboard",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private static string ResolvePython(string appDir)
    {
        string venvPython = Path.Combine(appDir, ".venv", "Scripts", "python.exe");
        if (File.Exists(venvPython) && IsUsablePython(venvPython)) return venvPython;

        string altVenvPython = Path.Combine(appDir, "venv", "Scripts", "python.exe");
        if (File.Exists(altVenvPython) && IsUsablePython(altVenvPython)) return altVenvPython;

        if (IsUsablePython("python")) return "python";
        if (IsUsablePython("py")) return "py";
        return "python";
    }

    private static bool IsUsablePython(string pythonExe)
    {
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = "--version",
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            using (Process process = Process.Start(psi))
            {
                if (process == null) return false;
                bool exited = process.WaitForExit(3000);
                return exited && process.ExitCode == 0;
            }
        }
        catch
        {
            return false;
        }
    }

    private static LoginInput PromptLogin()
    {
        using (Form form = new Form())
        using (Label emailLabel = new Label())
        using (TextBox emailBox = new TextBox())
        using (Label passwordLabel = new Label())
        using (TextBox passwordBox = new TextBox())
        using (Button startButton = new Button())
        using (Button cancelButton = new Button())
        {
            form.Text = "Difotoin Dashboard";
            form.StartPosition = FormStartPosition.CenterScreen;
            form.FormBorderStyle = FormBorderStyle.FixedDialog;
            form.MaximizeBox = false;
            form.MinimizeBox = false;
            form.ClientSize = new Size(390, 205);

            Label noteLabel = new Label();
            noteLabel.Text = "Isi credential yang nanti dipakai login di browser.";
            noteLabel.Location = new Point(20, 15);
            noteLabel.Size = new Size(350, 18);

            emailLabel.Text = "Email";
            emailLabel.Location = new Point(20, 45);
            emailLabel.AutoSize = true;

            emailBox.Location = new Point(20, 67);
            emailBox.Size = new Size(350, 24);
            emailBox.Text = Environment.GetEnvironmentVariable("DIFOTOIN_ADMIN_EMAIL") ?? DefaultEmail;

            passwordLabel.Text = "Password";
            passwordLabel.Location = new Point(20, 103);
            passwordLabel.AutoSize = true;

            passwordBox.Location = new Point(20, 125);
            passwordBox.Size = new Size(350, 24);
            passwordBox.UseSystemPasswordChar = true;

            startButton.Text = "Start";
            startButton.Location = new Point(214, 166);
            startButton.DialogResult = DialogResult.OK;

            cancelButton.Text = "Cancel";
            cancelButton.Location = new Point(295, 166);
            cancelButton.DialogResult = DialogResult.Cancel;

            form.Controls.AddRange(new Control[] {
                noteLabel, emailLabel, emailBox, passwordLabel, passwordBox, startButton, cancelButton
            });
            form.AcceptButton = startButton;
            form.CancelButton = cancelButton;

            if (form.ShowDialog() != DialogResult.OK)
            {
                return null;
            }

            if (string.IsNullOrWhiteSpace(emailBox.Text) || string.IsNullOrWhiteSpace(passwordBox.Text))
            {
                MessageBox.Show(
                    "Email dan password wajib diisi.",
                    "Difotoin Dashboard",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning);
                return null;
            }

            return new LoginInput
            {
                Email = emailBox.Text.Trim(),
                Password = passwordBox.Text
            };
        }
    }

    private class LoginInput
    {
        public string Email { get; set; }
        public string Password { get; set; }
    }

    private class StatusForm : Form
    {
        private Process server;
        private readonly string pythonExe;
        private readonly string appDir;
        private readonly LoginInput login;
        private readonly Label statusLabel;
        private readonly TextBox logBox;
        private readonly Button openButton;
        private readonly Button restartButton;
        private readonly Button stopButton;
        private readonly Timer timer;
        private bool browserOpened;
        private int elapsedSeconds;

        public StatusForm(string pythonExe, string appDir, LoginInput login)
        {
            this.pythonExe = pythonExe;
            this.appDir = appDir;
            this.login = login;

            Text = "Difotoin Dashboard Launcher";
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(620, 420);
            MinimumSize = new Size(620, 420);

            statusLabel = new Label();
            statusLabel.Text = "Status: starting server...";
            statusLabel.Location = new Point(20, 18);
            statusLabel.Size = new Size(570, 24);
            statusLabel.Font = new Font(statusLabel.Font, FontStyle.Bold);

            Label infoLabel = new Label();
            infoLabel.Text =
                "Tunggu sampai status Ready. Login browser pakai email " + login.Email +
                " dan password yang tadi diisi.";
            infoLabel.Location = new Point(20, 46);
            infoLabel.Size = new Size(570, 36);

            logBox = new TextBox();
            logBox.Location = new Point(20, 90);
            logBox.Size = new Size(580, 270);
            logBox.Multiline = true;
            logBox.ScrollBars = ScrollBars.Vertical;
            logBox.ReadOnly = true;
            logBox.Font = new Font("Consolas", 9);

            openButton = new Button();
            openButton.Text = "Open Dashboard";
            openButton.Location = new Point(240, 374);
            openButton.Size = new Size(115, 28);
            openButton.Enabled = false;
            openButton.Click += (sender, args) => OpenDashboard();

            restartButton = new Button();
            restartButton.Text = "Restart Server";
            restartButton.Location = new Point(365, 374);
            restartButton.Size = new Size(115, 28);
            restartButton.Click += (sender, args) => RestartServer();

            stopButton = new Button();
            stopButton.Text = "Stop Server";
            stopButton.Location = new Point(490, 374);
            stopButton.Size = new Size(110, 28);
            stopButton.Click += (sender, args) => Close();

            Controls.AddRange(new Control[] {
                statusLabel, infoLabel, logBox, openButton, restartButton, stopButton
            });

            timer = new Timer();
            timer.Interval = 1000;
            timer.Tick += CheckServer;

            FormClosing += (sender, args) => StopServer();
            StartServer();
        }

        private void StartServer()
        {
            ProcessStartInfo psi = new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = "-m streamlit run app.py --server.port 8501 --server.headless false",
                WorkingDirectory = appDir,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            psi.EnvironmentVariables["DIFOTOIN_ADMIN_EMAIL"] = login.Email;
            psi.EnvironmentVariables["DIFOTOIN_ADMIN_PASSWORD"] = login.Password;

            elapsedSeconds = 0;
            openButton.Enabled = false;
            statusLabel.Text = "Status: starting server...";

            server = Process.Start(psi);
            if (server == null)
            {
                statusLabel.Text = "Status: failed. Server tidak bisa dijalankan.";
                return;
            }

            server.OutputDataReceived += (sender, args) => AppendLog(args.Data);
            server.ErrorDataReceived += (sender, args) => AppendLog(args.Data);
            server.BeginOutputReadLine();
            server.BeginErrorReadLine();
            timer.Start();
        }

        public void AppendLog(string line)
        {
            if (string.IsNullOrWhiteSpace(line)) return;
            if (InvokeRequired)
            {
                BeginInvoke(new Action<string>(AppendLog), line);
                return;
            }

            logBox.AppendText(line + Environment.NewLine);
        }

        private void CheckServer(object sender, EventArgs args)
        {
            elapsedSeconds++;

            if (server == null || server.HasExited)
            {
                timer.Stop();
                statusLabel.Text = "Status: failed. Server berhenti sebelum dashboard ready.";
                openButton.Enabled = false;
                if (server != null) AppendLog("Process exited with code: " + server.ExitCode);
                AppendLog("Kalau ada pesan ModuleNotFoundError, jalankan pip install -r requirements.txt di folder streamlit_template.");
                return;
            }

            if (IsDashboardReady())
            {
                statusLabel.Text = "Status: ready. Dashboard aktif di " + DashboardUrl;
                openButton.Enabled = true;
                if (!browserOpened)
                {
                    OpenDashboard();
                }
                return;
            }

            statusLabel.Text = "Status: starting server... " + elapsedSeconds + "s";
        }

        private void RestartServer()
        {
            AppendLog("Restart requested. Stopping server...");
            StopServer();
            browserOpened = false;
            AppendLog("Starting server again...");
            StartServer();
        }

        private bool IsDashboardReady()
        {
            try
            {
                HttpWebRequest request = (HttpWebRequest)WebRequest.Create(DashboardUrl);
                request.Method = "GET";
                request.Timeout = 700;
                using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                {
                    return (int)response.StatusCode >= 200 && (int)response.StatusCode < 500;
                }
            }
            catch
            {
                return false;
            }
        }

        private void OpenDashboard()
        {
            browserOpened = true;
            Process.Start(new ProcessStartInfo
            {
                FileName = DashboardUrl,
                UseShellExecute = true
            });
        }

        private void StopServer()
        {
            timer.Stop();
            if (server != null && !server.HasExited)
            {
                try { server.Kill(); }
                catch { }
            }
            server = null;
        }
    }
}
