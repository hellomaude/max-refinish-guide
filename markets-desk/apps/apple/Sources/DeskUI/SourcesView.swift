import SwiftUI
import DeskKit

public struct SourcesView: View {
    @Bindable var store: DeskStore
    let now: Date
    public init(store: DeskStore, now: Date = Date()) { self.store = store; self.now = now }

    public var body: some View {
        List {
            if let snap = store.snapshot {
                Section(header: HStack { SectionHeader("Sources"); Spacer(); AgeLabel(snap.sources.generatedAt, now: now) }) {
                    if let rows = snap.sources.sources, !rows.isEmpty {
                        ForEach(rows) { s in
                            HStack {
                                Text(s.sourceId).font(.callout.monospaced())
                                Text(s.state).font(.caption.bold()).foregroundStyle(DeskColor.sourceState(s.state))
                                Spacer()
                                if let ms = s.latencyMs { Text("\(Int(ms))ms").font(.caption.monospacedDigit()).foregroundStyle(.secondary) }
                            }
                        }
                    } else {
                        Text("no preflight on file — run desk preflight").foregroundStyle(.secondary)
                    }
                }
                Section(header: SectionHeader("Event windows")) {
                    if snap.eventWindows.isEmpty { Text("none").foregroundStyle(.secondary) }
                    ForEach(snap.eventWindows) { w in
                        VStack(alignment: .leading) {
                            Text(w.id).font(.callout)
                            Text("\(w.startsAt.formatted(date: .abbreviated, time: .shortened)) → \(w.endsAt.formatted(date: .abbreviated, time: .shortened))").font(.caption).foregroundStyle(.secondary)
                            Text("binds: \(w.appliesToKinds.isEmpty ? "all" : w.appliesToKinds.joined(separator: ", "))").font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .refreshable { await store.refresh() }
    }
}
