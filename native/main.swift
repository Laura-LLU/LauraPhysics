import Cocoa
import UniformTypeIdentifiers
import WebKit

private let authorEmail = "LLUPAT@163.com"
private let authorGitHub = URL(string: "https://github.com/Laura-LLU")!

private struct Course {
    let shortTitle: String
    let windowTitle: String
    let address: String
    let projectRoot: String
    let serverScript: String
    let port: String
    let expectedHealthText: String
    let logName: String
}

private let localResources = Bundle.main.resourceURL!.path
private let courses = [
    Course(shortTitle: "AI 组卷与批改", windowTitle: "OPBP Bank · AI 组卷与评卷", address: "http://127.0.0.1:8785", projectRoot: localResources, serverScript: localResources + "/server.py", port: "8785", expectedHealthText: "OPBP Bank", logName: "LauraPhysicsOpen-AI.log"),
    Course(shortTitle: "OPBP 组卷", windowTitle: "OPBP Bank · OPBP 组卷", address: "http://127.0.0.1:8787", projectRoot: localResources, serverScript: localResources + "/server.py", port: "8787", expectedHealthText: "OPBP Bank", logName: "LauraPhysicsOpen-9702.log"),
]

final class FileDropOverlay: NSView {
    var fileDropHandler: (([URL]) -> Void)?
    var hoverHandler: ((Bool) -> Void)?
    var clickHandler: (() -> Void)?

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        registerForDraggedTypes([.fileURL])
        setAccessibilityLabel("AI 批改答卷上传区域")
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        registerForDraggedTypes([.fileURL])
    }

    private func droppedFileURLs(_ sender: NSDraggingInfo) -> [URL] {
        let options: [NSPasteboard.ReadingOptionKey: Any] = [.urlReadingFileURLsOnly: true]
        return sender.draggingPasteboard
            .readObjects(forClasses: [NSURL.self], options: options)?
            .compactMap { ($0 as? NSURL) as URL? }
            ?? []
    }

    override func draggingEntered(_ sender: NSDraggingInfo) -> NSDragOperation {
        guard !droppedFileURLs(sender).isEmpty else { return [] }
        hoverHandler?(true)
        return .copy
    }

    override func draggingUpdated(_ sender: NSDraggingInfo) -> NSDragOperation {
        guard !droppedFileURLs(sender).isEmpty else { return [] }
        hoverHandler?(true)
        return .copy
    }

    override func draggingExited(_ sender: NSDraggingInfo?) {
        hoverHandler?(false)
    }

    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {
        let urls = droppedFileURLs(sender)
        guard !urls.isEmpty else { return false }
        hoverHandler?(false)
        fileDropHandler?(urls)
        return true
    }

    override func mouseDown(with event: NSEvent) {
        clickHandler?()
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
    private var window: NSWindow!
    private var webView: WKWebView!
    private var webViews: [WKWebView] = []
    private var webContainer: NSView!
    private var fileDropOverlay: FileDropOverlay!
    private var courseSelector: NSSegmentedControl!
    private var selectedCourse = 0
    private var startedCourses = Set<Int>()
    private var readyCourses = Set<Int>()
    private var loadedCourses = Set<Int>()
    private var attempts: [Int: Int] = [:]
    private var serverProcesses: [Int: Process] = [:]
    private var extraWindows: [NSWindow] = []
    private var copyrightWindow: NSWindow?
    private var runtimePath: String?
    private let appSessionToken = UUID().uuidString

    private func findRuntime() -> String? {
        if let runtimePath = runtimePath { return runtimePath }
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let environment = ProcessInfo.processInfo.environment
        let data = environment["LAURAPHYSICS_OPEN_DATA"] ?? home + "/Library/Application Support/LauraPhysicsOpen"
        let candidates = [environment["LAURAPHYSICS_PYTHON"] ?? "", data + "/runtime/venv/bin/python3",
                          localResources + "/.venv/bin/python3",
                          home + "/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3",
                          "/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"]
        for path in candidates where FileManager.default.isExecutableFile(atPath: path) {
            let check = Process()
            check.executableURL = URL(fileURLWithPath: path)
            check.arguments = ["-B", localResources + "/environment_check.py"]
            check.standardOutput = FileHandle.nullDevice
            check.standardError = FileHandle.nullDevice
            do {
                try check.run()
                check.waitUntilExit()
                if check.terminationStatus == 0 { runtimePath = path; return path }
            } catch { continue }
        }
        return nil
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        installMainMenu()
        webContainer = NSView()
        webContainer.translatesAutoresizingMaskIntoConstraints = false
        for index in courses.indices {
            let configuration = WKWebViewConfiguration()
            configuration.websiteDataStore = .default()
            configuration.userContentController.add(self, name: "copyImage")
            configuration.userContentController.add(self, name: "fileDropZone")
            let courseView = WKWebView(frame: .zero, configuration: configuration)
            courseView.navigationDelegate = self
            courseView.uiDelegate = self
            courseView.translatesAutoresizingMaskIntoConstraints = false
            courseView.isHidden = index != selectedCourse
            webContainer.addSubview(courseView)
            NSLayoutConstraint.activate([
                courseView.topAnchor.constraint(equalTo: webContainer.topAnchor),
                courseView.leadingAnchor.constraint(equalTo: webContainer.leadingAnchor),
                courseView.trailingAnchor.constraint(equalTo: webContainer.trailingAnchor),
                courseView.bottomAnchor.constraint(equalTo: webContainer.bottomAnchor),
            ])
            webViews.append(courseView)
        }
        fileDropOverlay = FileDropOverlay(frame: .zero)
        fileDropOverlay.isHidden = true
        fileDropOverlay.fileDropHandler = { [weak self] urls in
            guard let self else { return }
            self.handleDroppedFiles(urls, in: self.webViews[0])
        }
        fileDropOverlay.hoverHandler = { [weak self] active in
            self?.setDropZoneHighlight(active)
        }
        fileDropOverlay.clickHandler = { [weak self] in
            self?.chooseMarkingFile()
        }
        webContainer.addSubview(fileDropOverlay, positioned: .above, relativeTo: nil)
        webView = webViews[selectedCourse]

        let topBar = NSVisualEffectView()
        topBar.material = .headerView
        topBar.blendingMode = .withinWindow
        topBar.state = .active
        topBar.translatesAutoresizingMaskIntoConstraints = false

        let courseLabel = NSTextField(labelWithString: "工作区")
        courseLabel.font = .systemFont(ofSize: 13, weight: .semibold)
        courseLabel.textColor = .secondaryLabelColor
        courseLabel.translatesAutoresizingMaskIntoConstraints = false

        courseSelector = NSSegmentedControl(
            labels: courses.map(\.shortTitle),
            trackingMode: .selectOne,
            target: self,
            action: #selector(courseChanged(_:))
        )
        courseSelector.selectedSegment = 0
        courseSelector.controlSize = .large
        courseSelector.translatesAutoresizingMaskIntoConstraints = false

        let copyrightButton = NSButton(title: "OPBP · 版权说明", target: self, action: #selector(showCopyright(_:)))
        copyrightButton.bezelStyle = .rounded
        copyrightButton.controlSize = .large
        copyrightButton.translatesAutoresizingMaskIntoConstraints = false

        let contactButton = NSButton(title: "Ⓛ  联系作者", target: self, action: #selector(showContact(_:)))
        contactButton.bezelStyle = .rounded
        contactButton.controlSize = .large
        contactButton.translatesAutoresizingMaskIntoConstraints = false

        topBar.addSubview(courseLabel)
        topBar.addSubview(courseSelector)
        topBar.addSubview(copyrightButton)
        topBar.addSubview(contactButton)

        let content = NSView()
        content.addSubview(topBar)
        content.addSubview(webContainer)
        NSLayoutConstraint.activate([
            topBar.topAnchor.constraint(equalTo: content.topAnchor),
            topBar.leadingAnchor.constraint(equalTo: content.leadingAnchor),
            topBar.trailingAnchor.constraint(equalTo: content.trailingAnchor),
            topBar.heightAnchor.constraint(equalToConstant: 54),
            courseLabel.leadingAnchor.constraint(equalTo: topBar.leadingAnchor, constant: 20),
            courseLabel.centerYAnchor.constraint(equalTo: topBar.centerYAnchor),
            courseSelector.leadingAnchor.constraint(equalTo: courseLabel.trailingAnchor, constant: 14),
            courseSelector.centerYAnchor.constraint(equalTo: topBar.centerYAnchor),
            courseSelector.widthAnchor.constraint(equalToConstant: 520),
            copyrightButton.leadingAnchor.constraint(greaterThanOrEqualTo: courseSelector.trailingAnchor, constant: 14),
            copyrightButton.trailingAnchor.constraint(equalTo: contactButton.leadingAnchor, constant: -12),
            copyrightButton.centerYAnchor.constraint(equalTo: topBar.centerYAnchor),
            contactButton.trailingAnchor.constraint(equalTo: topBar.trailingAnchor, constant: -20),
            contactButton.centerYAnchor.constraint(equalTo: topBar.centerYAnchor),
            webContainer.topAnchor.constraint(equalTo: topBar.bottomAnchor),
            webContainer.leadingAnchor.constraint(equalTo: content.leadingAnchor),
            webContainer.trailingAnchor.constraint(equalTo: content.trailingAnchor),
            webContainer.bottomAnchor.constraint(equalTo: content.bottomAnchor),
        ])

        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1320, height: 900),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = courses[0].windowTitle
        window.minSize = NSSize(width: 1000, height: 720)
        window.contentView = content
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        showStatus("正在打开 AI 助手…", detail: "OPBP题库会自动在本机启动。")
        for index in courses.indices {
            checkServer(index)
        }
    }

    private func installMainMenu() {
        let menu = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = NSMenu(title: "OPBP Bank")
        appMenu.addItem(withTitle: "OPBP 题库版权…", action: #selector(showCopyright(_:)), keyEquivalent: "")
        appMenu.addItem(withTitle: "联系作者…", action: #selector(showContact(_:)), keyEquivalent: "")
        appMenu.addItem(withTitle: "Laura-LLU 的 GitHub", action: #selector(openGitHub(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "退出 OPBP Bank", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        menu.addItem(appItem)

        let editItem = NSMenuItem()
        let editMenu = NSMenu(title: "编辑")
        editMenu.addItem(withTitle: "撤销", action: Selector(("undo:")), keyEquivalent: "z")
        let redoItem = editMenu.addItem(withTitle: "重做", action: Selector(("redo:")), keyEquivalent: "z")
        redoItem.keyEquivalentModifierMask = [.command, .shift]
        editMenu.addItem(.separator())
        editMenu.addItem(withTitle: "剪切", action: Selector(("cut:")), keyEquivalent: "x")
        editMenu.addItem(withTitle: "复制", action: Selector(("copy:")), keyEquivalent: "c")
        editMenu.addItem(withTitle: "粘贴", action: Selector(("paste:")), keyEquivalent: "v")
        editMenu.addItem(withTitle: "全选", action: Selector(("selectAll:")), keyEquivalent: "a")
        editItem.submenu = editMenu
        menu.addItem(editItem)
        NSApp.mainMenu = menu
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }

    @objc private func showCopyright(_ sender: Any?) {
        if let copyrightWindow {
            copyrightWindow.makeKeyAndOrderFront(nil)
            return
        }
        let view = WKWebView(frame: .zero)
        view.uiDelegate = self
        let panel = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1000, height: 720),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        panel.title = "OPBP · 题库版权"
        panel.isReleasedWhenClosed = false
        panel.minSize = NSSize(width: 760, height: 540)
        panel.contentView = view
        panel.center()
        panel.makeKeyAndOrderFront(nil)
        copyrightWindow = panel
        view.load(URLRequest(url: URL(string: courses[selectedCourse].address + "/copyright")!))
    }

    @objc private func showContact(_ sender: Any?) {
        let alert = NSAlert()
        alert.messageText = "联系 Laura-LLU"
        alert.informativeText = "邮箱：\(authorEmail)\nGitHub：github.com/Laura-LLU"
        alert.addButton(withTitle: "发送邮件")
        alert.addButton(withTitle: "打开 GitHub")
        alert.addButton(withTitle: "关闭")
        switch alert.runModal() {
        case .alertFirstButtonReturn:
            if let address = URL(string: "mailto:\(authorEmail)") { NSWorkspace.shared.open(address) }
        case .alertSecondButtonReturn:
            NSWorkspace.shared.open(authorGitHub)
        default:
            break
        }
    }

    @objc private func openGitHub(_ sender: Any?) {
        NSWorkspace.shared.open(authorGitHub)
    }

    func applicationWillTerminate(_ notification: Notification) {
        for process in serverProcesses.values where process.isRunning {
            process.terminate()
        }
    }

    @objc private func courseChanged(_ sender: NSSegmentedControl) {
        let next = max(0, sender.selectedSegment)
        if selectedCourse == 0 && next != 0 {
            sender.selectedSegment = selectedCourse
            webViews[0].evaluateJavaScript("window.physicsBankCanLeaveMarking ? window.physicsBankCanLeaveMarking() : true") { [weak self] result, error in
                guard let self = self, error == nil, result as? Bool == true else { return }
                self.activateCourse(next)
            }
            return
        }
        activateCourse(next)
    }

    private func activateCourse(_ index: Int) {
        selectedCourse = index
        courseSelector.selectedSegment = index
        let course = courses[selectedCourse]
        window.title = course.windowTitle
        selectCourseView(selectedCourse)
        if readyCourses.contains(selectedCourse) {
            loadCourse(selectedCourse)
        } else {
            showStatus("正在打开 \(course.shortTitle)…", detail: "正在连接这套本地题库。")
            checkServer(selectedCourse)
        }
    }

    private func checkServer(_ index: Int) {
        let course = courses[index]
        guard let url = URL(string: course.address + "/api/health") else { return }
        var request = URLRequest(url: url)
        request.timeoutInterval = 1.2
        URLSession.shared.dataTask(with: request) { [weak self] data, response, _ in
            guard let self else { return }
            let status = (response as? HTTPURLResponse)?.statusCode
            let body = data.flatMap { String(data: $0, encoding: .utf8) } ?? ""
            DispatchQueue.main.async {
                if status == 200 && body.contains(course.expectedHealthText) {
                    self.readyCourses.insert(index)
                    if self.selectedCourse == index {
                        self.loadCourse(index)
                    }
                    return
                }
                if !self.startedCourses.contains(index) {
                    self.startServer(index)
                }
                let count = (self.attempts[index] ?? 0) + 1
                self.attempts[index] = count
                if count < 34 {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { self.checkServer(index) }
                } else if self.selectedCourse == index {
                    self.showStatus(
                        "\(course.shortTitle) 没有成功启动",
                        detail: "请按安装说明检查运行环境，然后退出并重新打开。"
                    )
                }
            }
        }.resume()
    }

    private func startServer(_ index: Int) {
        let course = courses[index]
        startedCourses.insert(index)
        guard let pythonPath = findRuntime() else {
            attempts[index] = 40
            showStatus("需要设置运行环境", detail: "请按安装说明完成运行环境设置后重新打开；已保存的试卷仍会保留。")
            return
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: pythonPath)
        process.arguments = ["-B", course.serverScript, "--host", "127.0.0.1", "--port", course.port]
        process.currentDirectoryURL = URL(fileURLWithPath: course.projectRoot)

        let logURL = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Logs/" + course.logName)
        try? FileManager.default.createDirectory(at: logURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: logURL.path) {
            FileManager.default.createFile(atPath: logURL.path, contents: nil)
        }
        if let handle = try? FileHandle(forWritingTo: logURL) {
            _ = try? handle.seekToEnd()
            process.standardOutput = handle
            process.standardError = handle
        }

        do {
            try process.run()
            serverProcesses[index] = process
        } catch {
            attempts[index] = 40
            if selectedCourse == index {
                showStatus("\(course.shortTitle) 没有成功启动", detail: "本地服务启动失败：\(error.localizedDescription)")
            }
        }
    }

    private func loadCourse(_ index: Int) {
        guard selectedCourse == index else { return }
        selectCourseView(index)
        guard !loadedCourses.contains(index), var components = URLComponents(string: courses[index].address) else { return }
        components.queryItems = [URLQueryItem(name: "appSession", value: appSessionToken)]
        guard let url = components.url else { return }
        loadedCourses.insert(index)
        webViews[index].load(URLRequest(url: url))
    }

    private func selectCourseView(_ index: Int) {
        guard webViews.indices.contains(index) else { return }
        for (viewIndex, view) in webViews.enumerated() {
            view.isHidden = viewIndex != index
        }
        webView = webViews[index]
        if index != 0 {
            fileDropOverlay?.isHidden = true
        } else {
            webViews[0].evaluateJavaScript("window.physicsBankReportDropZone && window.physicsBankReportDropZone();")
        }
    }

    private func setDropZoneHighlight(_ active: Bool) {
        let value = active ? "true" : "false"
        webViews.first?.evaluateJavaScript("window.physicsBankNativeDropZoneActive && window.physicsBankNativeDropZoneActive(\(value));")
    }

    private func chooseMarkingFile() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = true
        panel.allowedContentTypes = [.pdf, .jpeg, .png]
        panel.message = "选择已完成的 OPBP 试卷"
        panel.prompt = "选择试卷"
        guard let window else { return }
        panel.beginSheetModal(for: window) { [weak self] response in
            guard response == .OK, !panel.urls.isEmpty, let self else { return }
            self.handleDroppedFiles(panel.urls, in: self.webViews[0])
        }
    }

    private func handleDroppedFiles(_ urls: [URL], in webView: WKWebView) {
        let mimeTypes = ["pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"]
        guard !urls.isEmpty, urls.count <= 12 else {
            webView.evaluateJavaScript("window.physicsBankNativeDropError && window.physicsBankNativeDropError('too-many');")
            return
        }
        guard urls.allSatisfy({ mimeTypes[$0.pathExtension.lowercased()] != nil }) else {
            webView.evaluateJavaScript("window.physicsBankNativeDropError && window.physicsBankNativeDropError('only-supported');")
            return
        }
        guard urls.allSatisfy({ ((try? $0.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0) <= 20 * 1024 * 1024 }) else {
            webView.evaluateJavaScript("window.physicsBankNativeDropError && window.physicsBankNativeDropError('too-large');")
            return
        }
        DispatchQueue.global(qos: .userInitiated).async {
            var payloads: [[String: Any]] = []
            for url in urls {
                let accessed = url.startAccessingSecurityScopedResource()
                defer { if accessed { url.stopAccessingSecurityScopedResource() } }
                guard let data = try? Data(contentsOf: url),
                      let mimeType = mimeTypes[url.pathExtension.lowercased()] else {
                    DispatchQueue.main.async {
                        webView.evaluateJavaScript("window.physicsBankNativeDropError && window.physicsBankNativeDropError('read-failed');")
                    }
                    return
                }
                payloads.append([
                    "name": url.lastPathComponent,
                    "mimeType": mimeType,
                    "base64": data.base64EncodedString(),
                ])
            }
            guard let jsonData = try? JSONSerialization.data(withJSONObject: payloads),
                  let json = String(data: jsonData, encoding: .utf8) else { return }
            DispatchQueue.main.async {
                webView.evaluateJavaScript("window.physicsBankHandleNativeDrop && window.physicsBankHandleNativeDrop(\(json));")
            }
        }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard let port = webView.url?.port,
              let index = courses.firstIndex(where: { Int($0.port) == port }) else { return }
        selectedCourse = index
        courseSelector.selectedSegment = index
        window.title = courses[index].windowTitle
    }

    private func showStatus(_ title: String, detail: String) {
        let html = """
        <!doctype html><meta charset="utf-8">
        <style>
          html,body{height:100%;margin:0;background:#172234;color:#f6f1e7;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}
          main{height:100%;display:grid;place-items:center;text-align:center} h1{font-family:Georgia,"Songti SC",serif;font-size:36px;margin:0 0 12px}
          p{color:#cbd3df;font-size:16px;margin:0}.line{width:84px;height:3px;background:#c85b48;margin:24px auto 0;border-radius:3px}
        </style><main><div><h1>\(title)</h1><p>\(detail)</p><div class="line"></div></div></main>
        """
        webView.loadHTMLString(html, baseURL: nil)
    }

    func webView(
        _ webView: WKWebView,
        createWebViewWith configuration: WKWebViewConfiguration,
        for navigationAction: WKNavigationAction,
        windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        guard navigationAction.targetFrame == nil, let url = navigationAction.request.url else { return nil }
        if url.host == "127.0.0.1" || url.host == "localhost" {
            let childWebView = WKWebView(frame: .zero, configuration: configuration)
            let childWindow = NSWindow(
                contentRect: NSRect(x: 0, y: 0, width: 1080, height: 780),
                styleMask: [.titled, .closable, .miniaturizable, .resizable],
                backing: .buffered,
                defer: false
            )
            childWindow.title = "OPBP Bank 文件"
            childWindow.contentView = childWebView
            childWindow.center()
            childWindow.makeKeyAndOrderFront(nil)
            extraWindows.append(childWindow)
            childWebView.load(navigationAction.request)
            return childWebView
        }
        NSWorkspace.shared.open(url)
        return nil
    }

    func webView(
        _ webView: WKWebView,
        runJavaScriptConfirmPanelWithMessage message: String,
        initiatedByFrame frame: WKFrameInfo,
        completionHandler: @escaping (Bool) -> Void
    ) {
        let alert = NSAlert()
        let isClearRequest = message.contains("清空")
        alert.alertStyle = isClearRequest ? .warning : .informational
        alert.messageText = isClearRequest ? "清空本次试题？" : "请确认"
        alert.informativeText = message
        alert.addButton(withTitle: isClearRequest ? "清空" : "确认")
        alert.addButton(withTitle: "取消")
        guard let window else {
            completionHandler(false)
            return
        }
        alert.beginSheetModal(for: window) { response in
            completionHandler(response == .alertFirstButtonReturn)
        }
    }

    func webView(
        _ webView: WKWebView,
        runOpenPanelWith parameters: WKOpenPanelParameters,
        initiatedByFrame frame: WKFrameInfo,
        completionHandler: @escaping ([URL]?) -> Void
    ) {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.allowedContentTypes = [.pdf, .jpeg, .png]
        panel.message = "选择已完成的 0625 或 9702 试卷"
        panel.prompt = "选择试卷"
        guard let window else {
            completionHandler(nil)
            return
        }
        panel.beginSheetModal(for: window) { response in
            completionHandler(response == .OK ? panel.urls : nil)
        }
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        if message.name == "fileDropZone" {
            updateFileDropZone(message.body, from: message.webView)
            return
        }
        guard message.name == "copyImage",
              let relativeAddress = message.body as? String,
              let baseURL = webView.url,
              let imageURL = URL(string: relativeAddress, relativeTo: baseURL)?.absoluteURL else {
            reportCopyResult(false)
            return
        }

        URLSession.shared.dataTask(with: imageURL) { [weak self] data, response, _ in
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            guard status == 200, let data, let image = NSImage(data: data) else {
                DispatchQueue.main.async { self?.reportCopyResult(false) }
                return
            }
            DispatchQueue.main.async {
                let pasteboard = NSPasteboard.general
                pasteboard.clearContents()
                self?.reportCopyResult(pasteboard.writeObjects([image]))
            }
        }.resume()
    }

    private func updateFileDropZone(_ body: Any, from sourceWebView: WKWebView?) {
        guard selectedCourse == 0,
              sourceWebView === webViews.first,
              let values = body as? [String: Any],
              (values["visible"] as? Bool) == true,
              let x = (values["x"] as? NSNumber)?.doubleValue,
              let y = (values["y"] as? NSNumber)?.doubleValue,
              let width = (values["width"] as? NSNumber)?.doubleValue,
              let height = (values["height"] as? NSNumber)?.doubleValue,
              let viewportWidth = (values["viewportWidth"] as? NSNumber)?.doubleValue,
              let viewportHeight = (values["viewportHeight"] as? NSNumber)?.doubleValue,
              width > 0, height > 0, viewportWidth > 0, viewportHeight > 0 else {
            fileDropOverlay?.isHidden = true
            return
        }
        let scaleX = webViews[0].bounds.width / viewportWidth
        let scaleY = webViews[0].bounds.height / viewportHeight
        let frame = NSRect(
            x: x * scaleX,
            y: webViews[0].bounds.height - ((y + height) * scaleY),
            width: width * scaleX,
            height: height * scaleY
        ).intersection(webViews[0].bounds)
        guard !frame.isEmpty else {
            fileDropOverlay.isHidden = true
            return
        }
        fileDropOverlay.frame = frame
        fileDropOverlay.isHidden = false
    }

    private func reportCopyResult(_ succeeded: Bool) {
        let value = succeeded ? "true" : "false"
        webView.evaluateJavaScript("window.physicsBankCopyResult && window.physicsBankCopyResult(\(value));")
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
