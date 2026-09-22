// The client of `desk serve`. Every call but one is a GET. The one POST is
// the confirm, and it is the only place in either app that sends a body.
// `tests/test_apple.py` on the Python side counts that.
import Foundation

public enum DeskAPIError: Error, LocalizedError, Sendable {
    case notPaired
    case http(Int, String)
    case transport(String)
    case decoding(String)

    public var errorDescription: String? {
        switch self {
        case .notPaired: return "Not paired. Scan the code the Mac shows."
        case .http(let code, let msg): return "\(code): \(msg)"
        case .transport(let msg): return msg
        case .decoding(let msg): return "Bad response: \(msg)"
        }
    }
}

public struct DeskAPI: Sendable {
    public let pairing: Pairing
    private let session: URLSession

    public init(pairing: Pairing, session: URLSession = .shared) {
        self.pairing = pairing
        self.session = session
    }

    public func snapshot() async throws -> Snapshot {
        try await get("/api/snapshot", as: Snapshot.self)
    }

    public func health() async throws -> [String: Bool] {
        struct H: Codable { var ok: Bool; var paired: Bool }
        let h = try await get("/api/health", as: H.self)
        return ["ok": h.ok, "paired": h.paired]
    }

    /// The one write. The digest is what the screen was showing; the server
    /// refuses if the book has moved since, and that refusal is the point.
    public func confirm(_ request: ConfirmRequest) async throws -> ConfirmResponse {
        var req = URLRequest(url: pairing.baseURL.appending(path: "/confirm"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(pairing.token)", forHTTPHeaderField: "Authorization")
        req.httpBody = try JSONEncoder().encode(request)
        req.timeoutInterval = 10
        let (data, response) = try await perform(req)
        let decoded = try DeskJSON.decoder().decode(ConfirmResponse.self, from: data)
        if response.statusCode != 201 {
            throw DeskAPIError.http(response.statusCode, decoded.error ?? "refused")
        }
        return decoded
    }

    private func get<T: Decodable>(_ path: String, as type: T.Type) async throws -> T {
        var req = URLRequest(url: pairing.baseURL.appending(path: path))
        req.timeoutInterval = 10
        req.cachePolicy = .reloadIgnoringLocalCacheData
        let (data, response) = try await perform(req)
        guard response.statusCode == 200 else {
            throw DeskAPIError.http(response.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        do { return try DeskJSON.decoder().decode(T.self, from: data) }
        catch { throw DeskAPIError.decoding(String(describing: error)) }
    }

    private func perform(_ req: URLRequest) async throws -> (Data, HTTPURLResponse) {
        do {
            let (data, resp) = try await session.data(for: req)
            guard let http = resp as? HTTPURLResponse else { throw DeskAPIError.transport("no HTTP response") }
            return (data, http)
        } catch let e as DeskAPIError { throw e }
        catch { throw DeskAPIError.transport(error.localizedDescription) }
    }
}
