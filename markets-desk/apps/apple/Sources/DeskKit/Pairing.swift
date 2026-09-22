// The pairing: a base URL and a token, in the Keychain, and nothing else.
// The phone never holds a model, an API key, a broker credential, or the
// pack. This file is the whole of what it holds.
import Foundation
import Security

public struct Pairing: Sendable, Equatable {
    public var baseURL: URL
    public var token: String

    public init(baseURL: URL, token: String) { self.baseURL = baseURL; self.token = token }

    /// Parse the one-time URL `desk pair` prints: http://host:port/?token=…
    public static func parse(_ text: String) -> Pairing? {
        guard let url = URL(string: text.trimmingCharacters(in: .whitespacesAndNewlines)),
              let comps = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let token = comps.queryItems?.first(where: { $0.name == "token" })?.value,
              !token.isEmpty,
              let scheme = comps.scheme, let host = comps.host else { return nil }
        var base = URLComponents()
        base.scheme = scheme; base.host = host; base.port = comps.port
        guard let baseURL = base.url else { return nil }
        return Pairing(baseURL: baseURL, token: token)
    }
}

public enum Keychain {
    static let service = "com.maxmotif.desk"
    static let account = "pairing"

    public static func save(_ pairing: Pairing) throws {
        let payload = try JSONEncoder().encode(["base": pairing.baseURL.absoluteString, "token": pairing.token])
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
        var add = query
        add[kSecValueData as String] = payload
        add[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        let status = SecItemAdd(add as CFDictionary, nil)
        guard status == errSecSuccess else { throw KeychainError.status(status) }
    }

    public static func load() -> Pairing? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data,
              let dict = try? JSONDecoder().decode([String: String].self, from: data),
              let base = dict["base"], let url = URL(string: base), let token = dict["token"] else { return nil }
        return Pairing(baseURL: url, token: token)
    }

    public static func clear() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
    }

    public enum KeychainError: Error { case status(OSStatus) }
}
