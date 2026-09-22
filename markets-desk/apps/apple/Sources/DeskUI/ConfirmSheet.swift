// The gate. Four deliberate steps on purpose: read the stamp, read Jev,
// hold, biometrics. A market order should not be a swipe.
import SwiftUI
import DeskKit
import LocalAuthentication

public struct ConfirmSheet: View {
    @Bindable var store: DeskStore
    let stamp: StampInfo
    let jev: String?
    @Environment(\.dismiss) private var dismiss
    @State private var held = false
    @State private var holding = false
    @State private var progress: Double = 0
    @State private var outcome: String?
    @State private var busy = false

    public init(store: DeskStore, stamp: StampInfo, jev: String?) {
        self.store = store; self.stamp = stamp; self.jev = jev
    }

    public var body: some View {
        NavigationStack {
            List {
                Section(header: SectionHeader("You are confirming")) {
                    LabeledContent("ticket", value: stamp.ticketId)
                    LabeledContent("verdict") { Text(stamp.verdict.uppercased()).foregroundStyle(DeskColor.verdict(stamp.verdict)) }
                    LabeledContent("ceiling") { Pct(stamp.allowedPct, bold: true) }
                    LabeledContent("theme", value: stamp.theme)
                    LabeledContent("binding", value: stamp.bindingConstraint)
                    LabeledContent("conviction", value: "\(stamp.effectiveConfidence)/5")
                    LabeledContent("digest", value: String(stamp.stampSha256.prefix(12)) + "…").font(.caption.monospaced())
                }
                if !stamp.challengeVerdict.isEmpty {
                    Section(header: SectionHeader("The case against")) {
                        Text("Jev: \(stamp.challengeVerdict)").font(.callout)
                        if let jev { Text(jev).font(.callout).foregroundStyle(.secondary) }
                    }
                }
                Section {
                    Text("A confirm is a ceiling, not an order. It is good for one session and void if the book moves. A sheet is written only from it, and every venue is still paper unless MODE.yaml says otherwise.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Section {
                    if let outcome {
                        Text(outcome).font(.callout)
                    } else {
                        HoldToConfirm(progress: $progress, holding: $holding, held: $held, enabled: stamp.confirmable && !busy)
                            .onChange(of: held) { _, done in if done { Task { await run() } } }
                    }
                }
            }
            .navigationTitle("Confirm")
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } } }
        }
    }

    private func run() async {
        busy = true
        defer { busy = false }
        guard await biometric() else { outcome = "Face ID / Touch ID did not pass. Nothing sent."; held = false; return }
        switch await store.confirm(stamp) {
        case .success(let r):
            outcome = "Confirmed \(r.ticketId ?? stamp.ticketId) at \(String(format: "%.2f%%", r.allowedPct ?? stamp.allowedPct)). Written \(r.written ?? "")."
        case .failure(let e):
            outcome = "Refused: \(e.localizedDescription)"
            held = false
        }
    }

    private func biometric() async -> Bool {
        let ctx = LAContext()
        var err: NSError?
        guard ctx.canEvaluatePolicy(.deviceOwnerAuthentication, error: &err) else { return false }
        return (try? await ctx.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: "Confirm \(stamp.ticketId)")) ?? false
    }
}

struct HoldToConfirm: View {
    @Binding var progress: Double
    @Binding var holding: Bool
    @Binding var held: Bool
    let enabled: Bool
    private let duration: Double = 1.5

    var body: some View {
        ZStack(alignment: .leading) {
            RoundedRectangle(cornerRadius: 10).fill(Color.secondary.opacity(0.15))
            GeometryReader { g in
                RoundedRectangle(cornerRadius: 10).fill(DeskColor.accent.opacity(0.6))
                    .frame(width: g.size.width * progress)
            }
            Text(held ? "confirming" : (holding ? "hold…" : "hold to confirm")).frame(maxWidth: .infinity)
                .font(.body.bold())
        }
        .frame(height: 52)
        .opacity(enabled ? 1 : 0.35)
        .gesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in
                    guard enabled, !holding, !held else { return }
                    holding = true
                    withAnimation(.linear(duration: duration)) { progress = 1 }
                    Task {
                        try? await Task.sleep(for: .seconds(duration))
                        if holding && !held { held = true }
                    }
                }
                .onEnded { _ in
                    if !held { holding = false; withAnimation(.easeOut(duration: 0.15)) { progress = 0 } }
                }
        )
    }
}
