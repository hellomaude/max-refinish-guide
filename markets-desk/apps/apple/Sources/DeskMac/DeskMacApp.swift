// The Mac app. On the box it could read the desk directory directly; it
// reads `desk serve` on loopback instead so the two apps share one client
// and one data model, and so a second Mac works without code changes.
import SwiftUI
import DeskKit
import DeskUI

@main
struct DeskMacApp: App {
    @State private var store = DeskStore(device: "mac")

    var body: some Scene {
        WindowGroup("Markets Desk") {
            RootView(store: store)
                .frame(minWidth: 820, minHeight: 560)
        }
        .defaultSize(width: 1100, height: 720)
    }
}

enum Panel: String, CaseIterable, Identifiable {
    case book = "Book", seats = "Seats", sources = "Sources", ledger = "Ledger", mode = "Mode"
    var id: String { rawValue }
    var symbol: String {
        switch self {
        case .book: return "list.bullet.rectangle"; case .seats: return "person.3"
        case .sources: return "antenna.radiowaves.left.and.right"; case .ledger: return "tablecells"
        case .mode: return "slider.horizontal.3"
        }
    }
}

struct RootView: View {
    @Bindable var store: DeskStore
    @State private var panel: Panel? = .book

    var body: some View {
        NavigationSplitView {
            List(Panel.allCases, selection: $panel) { p in
                Label(p.rawValue, systemImage: p.symbol)
            }
            .navigationSplitViewColumnWidth(min: 160, ideal: 180)
        } detail: {
            Group {
                switch panel ?? .book {
                case .book: BookView(store: store)
                case .seats: SeatsView(store: store)
                case .sources: SourcesView(store: store)
                case .ledger: LedgerView(store: store)
                case .mode: ModeView(store: store)
                }
            }
            .toolbar {
                ToolbarItem { Button { Task { await store.refresh() } } label: { Image(systemName: "arrow.clockwise") } }
                ToolbarItem { AgeLabel(store.fetchedAt) }
            }
        }
        .task { if !store.paired { store.pairFromLoopbackIfPresent() } ; await store.refresh() }
    }
}

extension DeskStore {
    /// On the box, `desk pair` writes state/pair.token. If the app can read
    /// it from the desk root it pairs itself to loopback; otherwise Max
    /// pastes the URL like on the phone.
    func pairFromLoopbackIfPresent() {
        // In order: the env `open --env` passes, the file the launcher writes
        // (for Dock launches, which carry no env), then the default clone path.
        let recorded = try? String(contentsOfFile: NSHomeDirectory() + "/.config/markets-desk/root", encoding: .utf8)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let candidates = [
            ProcessInfo.processInfo.environment["DESK_ROOT"],
            recorded.flatMap { $0.isEmpty ? nil : $0 },
            NSHomeDirectory() + "/desk/markets-desk",
        ].compactMap { $0 }
        for root in candidates {
            let path = root + "/state/pair.token"
            if let token = try? String(contentsOfFile: path, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines), !token.isEmpty {
                _ = pair(with: "http://127.0.0.1:8791/?token=\(token)")
                return
            }
        }
    }
}
