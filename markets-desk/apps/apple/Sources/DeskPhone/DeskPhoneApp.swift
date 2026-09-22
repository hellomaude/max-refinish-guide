// The iPhone app. A client of `desk serve` over the tailnet. It holds the
// pairing in the Keychain and nothing else: no model, no key, no pack.
import SwiftUI
import DeskKit
import DeskUI

@main
struct DeskPhoneApp: App {
    @State private var store = DeskStore(device: "iphone")

    var body: some Scene {
        WindowGroup {
            TabView {
                NavigationStack { BookView(store: store).navigationTitle("Book") }
                    .tabItem { Label("Book", systemImage: "list.bullet.rectangle") }
                NavigationStack { SeatsView(store: store).navigationTitle("Seats") }
                    .tabItem { Label("Seats", systemImage: "person.3") }
                NavigationStack { SourcesView(store: store).navigationTitle("Sources") }
                    .tabItem { Label("Sources", systemImage: "antenna.radiowaves.left.and.right") }
                NavigationStack { LedgerView(store: store).navigationTitle("Ledger") }
                    .tabItem { Label("Ledger", systemImage: "tablecells") }
                NavigationStack { ModeView(store: store).navigationTitle("Mode") }
                    .tabItem { Label("Mode", systemImage: "slider.horizontal.3") }
            }
            .task { await store.refresh() }
            .onOpenURL { url in
                // The pairing URL from the Mac, opened from a scan or a tap.
                _ = store.pair(with: url.absoluteString)
                Task { await store.refresh() }
            }
        }
    }
}
