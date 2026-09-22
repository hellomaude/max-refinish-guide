import SwiftUI
import DeskKit

public struct ModeView: View {
    @Bindable var store: DeskStore
    let now: Date
    public init(store: DeskStore, now: Date = Date()) { self.store = store; self.now = now }

    public var body: some View {
        List {
            if let snap = store.snapshot {
                Section(header: SectionHeader("Mode")) {
                    LiveBanner(snap.mode.liveVenues)
                    LabeledContent("mode", value: snap.mode.mode)
                    LabeledContent("execution", value: snap.mode.execution)
                    LabeledContent("require_challenge", value: snap.mode.requireChallenge ? "true" : "false")
                    LabeledContent("required seats", value: snap.mode.requiredSeats.joined(separator: ", "))
                    LabeledContent("updated") { AgeLabel(snap.mode.updatedAt, now: now) }
                }
                Section(header: SectionHeader("Venues")) {
                    ForEach(snap.mode.venues.keys.sorted(), id: \.self) { id in
                        let v = snap.mode.venues[id]!
                        HStack {
                            Text(id).font(.callout.monospaced())
                            Spacer()
                            Text(v.enabled ? "enabled" : "disabled").font(.caption).foregroundStyle(.secondary)
                            if v.live { Text("LIVE").font(.caption.bold()).foregroundStyle(.white).padding(.horizontal, 6).background(DeskColor.fail, in: Capsule()) }
                            else { Text("live: false").font(.caption).foregroundStyle(DeskColor.pass) }
                        }
                    }
                }
                Section {
                    Text("This app cannot edit policy. Arming a venue is a text edit to MODE.yaml on the Mac, by Max, and the boundary test notices.").font(.caption).foregroundStyle(.secondary)
                }
            }
            Section(header: SectionHeader("Pairing")) {
                PairingView(store: store)
            }
        }
        .refreshable { await store.refresh() }
    }
}

public struct PairingView: View {
    @Bindable var store: DeskStore
    @State private var pasted = ""
    @State private var failed = false
    public init(store: DeskStore) { self.store = store }

    public var body: some View {
        if let p = store.pairing {
            LabeledContent("desk", value: p.baseURL.absoluteString)
            Button("Unpair", role: .destructive) { store.unpair() }
        } else {
            Text("Paste the one-time URL from `desk pair`.").font(.caption).foregroundStyle(.secondary)
            TextField("http://100.x.y.z:8791/?token=…", text: $pasted)
                .textFieldStyle(.roundedBorder)
                .autocorrectionDisabled()
            Button("Pair") { failed = !store.pair(with: pasted); if !failed { Task { await store.refresh() } } }
                .disabled(pasted.isEmpty)
            if failed { Text("That is not a pairing URL.").font(.caption).foregroundStyle(DeskColor.fail) }
        }
    }
}
