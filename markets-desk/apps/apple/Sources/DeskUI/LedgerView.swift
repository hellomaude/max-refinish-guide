import SwiftUI
import DeskKit

public struct LedgerView: View {
    @Bindable var store: DeskStore
    public init(store: DeskStore) { self.store = store }

    public var body: some View {
        List {
            if let snap = store.snapshot, let tables = snap.ledger.tables, !tables.isEmpty {
                ForEach(tables.keys.sorted(), id: \.self) { dim in
                    Section(header: SectionHeader("by \(dim)")) {
                        ForEach(tables[dim]!) { row in
                            HStack {
                                Text(row.key).font(.callout)
                                Spacer()
                                Text("n=\(row.resolved)").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                                Text(row.expectancyR.isEmpty ? "—" : row.expectancyR + "R").font(.caption.monospacedDigit())
                                Text(row.totalR + "R").font(.caption.monospacedDigit().bold())
                            }
                        }
                    }
                }
                if let lines = snap.ledger.lines {
                    Section { ForEach(lines, id: \.self) { Text($0).font(.caption).foregroundStyle(.secondary) } }
                }
            } else {
                Section { Text("no outcomes yet — the ledger scores forward only").foregroundStyle(.secondary) }
            }
        }
        .refreshable { await store.refresh() }
    }
}
