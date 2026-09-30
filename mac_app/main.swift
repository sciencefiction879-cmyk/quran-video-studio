import Cocoa
import WebKit

class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    var window: NSWindow!
    var webView: WKWebView!
    var serverProcess: Process?


    func applicationDidFinishLaunching(_ notification: Notification) {
        setupWindow()
        setupMenu()
        startServerAndLoad()
    }

    func findPythonBinary() -> String {
        let candidates = [
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "/usr/bin/python3"
        ]
        for c in candidates {
            if FileManager.default.fileExists(atPath: c) {
                return c
            }
        }
        return "/usr/bin/python3"
    }

    func isServerAlive() -> Bool {
        guard let url = URL(string: "http://localhost:8765/api/status") else { return false }
        var alive = false
        let sema = DispatchSemaphore(value: 0)
        let task = URLSession.shared.dataTask(with: url) { _, resp, _ in
            if let httpResp = resp as? HTTPURLResponse, httpResp.statusCode == 200 {
                alive = true
            }
            sema.signal()
        }
        task.resume()
        _ = sema.wait(timeout: .now() + 0.4)
        return alive
    }

    func startServerAndLoad() {
        if isServerAlive() {
            loadStudioUrl()
            return
        }

        // Locate server.py in Bundle or Workspace
        let bundlePath = Bundle.main.bundlePath
        var serverScript = (bundlePath as NSString).appendingPathComponent("Contents/Resources/server.py")
        if !FileManager.default.fileExists(atPath: serverScript) {
            serverScript = "/Users/shaddo/.gemini/antigravity/scratch/surah_fatiha/server.py"
        }

        if FileManager.default.fileExists(atPath: serverScript) {
            let proc = Process()
            let pyBin = findPythonBinary()
            proc.executableURL = URL(fileURLWithPath: pyBin)
            proc.arguments = [serverScript, "8765"]
            
            var env = ProcessInfo.processInfo.environment
            env["PATH"] = "/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
            proc.environment = env

            let workingDir = (serverScript as NSString).deletingLastPathComponent
            proc.currentDirectoryURL = URL(fileURLWithPath: workingDir)
            do {
                try proc.run()
                self.serverProcess = proc
            } catch {
                print("Could not start server:", error)
            }
        }

        // Show immediate warm loading splash
        showLoadingSplash()

        // Wait in background thread until server responds, then load
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            let start = Date()
            var ready = false
            while Date().timeIntervalSince(start) < 12.0 {
                if self.isServerAlive() {
                    ready = true
                    break
                }
                Thread.sleep(forTimeInterval: 0.25)
            }

            DispatchQueue.main.async {
                self.loadStudioUrl()
            }
        }
    }

    func showLoadingSplash() {
        let splashHtml = """
        <!DOCTYPE html>
        <html lang="ur" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <style>
                body { background: #04060b; color: #ffd700; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; text-align: center; }
                .spinner { width: 52px; height: 52px; border: 3px solid rgba(212,175,55,0.2); border-top-color: #ffd700; border-radius: 50%; animation: spin 0.9s infinite linear; margin-bottom: 22px; }
                @keyframes spin { 100% { transform: rotate(360deg); } }
                h1 { font-size: 2.2rem; margin: 0 0 10px 0; color: #ffffff; letter-spacing: 1px; }
                .gold-sub { color: #d4af37; font-size: 1.15rem; font-weight: 600; margin-bottom: 12px; }
                p { color: #94a3b8; font-size: 0.95rem; margin: 0; }
            </style>
        </head>
        <body>
            <div class="spinner"></div>
            <h1>القرآن الكريم</h1>
            <div class="gold-sub">✨ Quran Video Studio v1.3 (Professional Edition)</div>
            <p>اسٹوڈیو لوڈ ہو رہا ہے، برائے مہربانی چند سیکنڈ انتظار فرمائیں...</p>
        </body>
        </html>
        """
        webView.loadHTMLString(splashHtml, baseURL: nil)
    }

    func loadStudioUrl() {
        if let studioUrl = URL(string: "http://localhost:8765") {
            webView.load(URLRequest(url: studioUrl))
        }
    }

    func setupWindow() {
        let rect = NSRect(x: 100, y: 100, width: 1440, height: 900)
        window = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = "القرآن الكريم • Quran Video Studio v1.3 (Professional Edition)"
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.backgroundColor = NSColor(red: 4/255, green: 6/255, blue: 11/255, alpha: 1.0)
        window.center()
        window.isReleasedWhenClosed = false

        let config = WKWebViewConfiguration()
        config.preferences.setValue(true, forKey: "developerExtrasEnabled")
        
        webView = WKWebView(frame: window.contentView!.bounds, configuration: config)
        webView.autoresizingMask = [.width, .height]
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.setValue(false, forKey: "drawsBackground")

        window.contentView?.addSubview(webView)

        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func setupMenu() {
        let menubar = NSMenu()
        let appMenuItem = NSMenuItem()
        menubar.addItem(appMenuItem)
        NSApp.mainMenu = menubar

        let appMenu = NSMenu()
        let appName = "Quran Video Studio v1.4"
        appMenu.addItem(NSMenuItem(title: "About \(appName)", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: ""))
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(NSMenuItem(title: "Quit \(appName)", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))
        appMenuItem.submenu = appMenu

        // View Menu
        let viewMenuItem = NSMenuItem()
        menubar.addItem(viewMenuItem)
        let viewMenu = NSMenu(title: "View")
        let reloadItem = NSMenuItem(title: "Reload Studio", action: #selector(reloadPage), keyEquivalent: "r")
        reloadItem.target = self
        viewMenu.addItem(reloadItem)
        let fullScreenItem = NSMenuItem(title: "Toggle Full Screen", action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f")
        fullScreenItem.keyEquivalentModifierMask = [.command, .control]
        viewMenu.addItem(fullScreenItem)
        viewMenuItem.submenu = viewMenu
    }

    @objc func reloadPage() {
        webView.reload()
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        print("Provisional navigation error:", error.localizedDescription)
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
            self?.loadStudioUrl()
        }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        print("Navigation failed:", error.localizedDescription)
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
            self?.loadStudioUrl()
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, preferences: WKWebpagePreferences, decisionHandler: @escaping (WKNavigationActionPolicy, WKWebpagePreferences) -> Void) {
        if navigationAction.shouldPerformDownload {
            decisionHandler(.download, preferences)
            return
        }
        decisionHandler(.allow, preferences)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        if let mime = navigationResponse.response.mimeType, mime.contains("video") || mime.contains("audio") {
            decisionHandler(.allow)
            return
        }
        if navigationResponse.canShowMIMEType {
            decisionHandler(.allow)
        } else {
            decisionHandler(.download)
        }
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
        download.delegate = self
    }

    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        download.delegate = self
    }

    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let downloads = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first!
        let dest = downloads.appendingPathComponent(suggestedFilename)
        completionHandler(dest)
    }

    func downloadDidFinish(_ download: WKDownload) {
        print("Download finished successfully!")
    }

    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        print("Download error:", error.localizedDescription)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }


    func applicationWillTerminate(_ notification: Notification) {
        serverProcess?.terminate()
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
