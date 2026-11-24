// Approval robot (the "worker" service).
//
// Every WORKER_INTERVAL_SECONDS seconds it reads the pending registrations from
// the backend and approves the ones whose profile is complete. The other ones
// stay pending for the administrators. The robot has an account of its own and
// signs in with its API key, and the backend refuses any request that the
// permissions of that account do not allow, so a mistake here cannot approve
// an incomplete profile.

#include <curl/curl.h>
#include <nlohmann/json.hpp>

#include <csignal>
#include <cstdlib>
#include <iostream>
#include <string>
#include <unistd.h>

using json = nlohmann::json;

static volatile sig_atomic_t stop_requested = 0;

static void handle_signal(int) { stop_requested = 1; }

// Levels of the log, from the most detailed to the most serious.
enum class Level { Debug, Info, Warn, Error };

static Level minimum_level = Level::Info;

// Writes a line when its level reaches the minimum. Warnings and errors go to the error output.
static void log(Level level, const std::string& message) {
    if (level < minimum_level) return;
    const char* names[] = {"DEBUG", "INFO", "WARN", "ERROR"};
    std::ostream& out = level >= Level::Warn ? std::cerr : std::cout;
    out << "[" << names[static_cast<int>(level)] << "] " << message << std::endl;
}

// Reads the minimum level from LOG_LEVEL and returns false when the value is not a level.
static bool read_level(const char* text, Level* level) {
    const std::string name = text ? text : "INFO";
    if (name == "DEBUG") *level = Level::Debug;
    else if (name == "INFO") *level = Level::Info;
    else if (name == "WARN") *level = Level::Warn;
    else if (name == "ERROR") *level = Level::Error;
    else return false;
    return true;
}

static size_t collect(char* data, size_t size, size_t count, void* target) {
    static_cast<std::string*>(target)->append(data, size * count);
    return size * count;
}

// Status code and body of an answer. A code of 0 means that no answer arrived.
struct Reply {
    long code = 0;
    std::string body;
};

// Sends a GET or an empty POST with the API key in the Authorization header.
static Reply send_request(const std::string& method, const std::string& url, const std::string& api_key) {
    Reply reply;
    CURL* curl = curl_easy_init();
    if (!curl) return reply;

    std::string header = "Authorization: Bearer " + api_key;
    curl_slist* headers = curl_slist_append(nullptr, header.c_str());
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_PROTOCOLS_STR, "http,https");
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, collect);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &reply.body);
    if (method == "POST") {
        curl_easy_setopt(curl, CURLOPT_POST, 1L);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, "");
    }

    if (curl_easy_perform(curl) == CURLE_OK) {
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &reply.code);
    }
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    return reply;
}

// A field is present when it is a text with at least one character that is not a space.
static bool is_present(const json& registration, const char* field) {
    if (!registration.contains(field) || !registration.at(field).is_string()) return false;
    const std::string text = registration.at(field).get<std::string>();
    return text.find_first_not_of(" \t\r\n") != std::string::npos;
}

// The profile is complete when the organization and the country are present.
static bool is_profile_complete(const json& registration) {
    return is_present(registration, "organization") && is_present(registration, "country");
}

// Reads the list of the backend and returns false when the answer cannot be used.
static bool read_registrations(const Reply& reply, json* registrations) {
    if (reply.code != 200) {
        log(Level::Error, "The backend responded " + std::to_string(reply.code) + " to the list");
        return false;
    }
    json data = json::parse(reply.body, nullptr, false);
    if (data.is_discarded() || !data.is_object() || !data.contains("registrations") ||
        !data.at("registrations").is_array()) {
        log(Level::Error, "The list has an unexpected format");
        return false;
    }
    *registrations = data.at("registrations");
    return true;
}

static void run_cycle(const std::string& backend, const std::string& api_key) {
    json registrations;
    if (!read_registrations(send_request("GET", backend + "/api/internal/registrations", api_key), &registrations)) {
        return;
    }

    int approved = 0, skipped = 0, refused = 0, already_reviewed = 0, failed = 0;
    for (const json& registration : registrations) {
        if (!registration.is_object() || !registration.contains("id") || !registration.at("id").is_number_integer()) {
            failed++;
            log(Level::Warn, "A registration without a valid id was ignored");
            continue;
        }
        long long id = registration.at("id").get<long long>();

        // The decision is made here and the backend checks it again.
        if (!is_profile_complete(registration)) {
            skipped++;
            log(Level::Debug, "Account " + std::to_string(id) + " is left for the administrators");
            continue;
        }
        Reply reply = send_request("POST", backend + "/api/internal/registrations/" + std::to_string(id) + "/approve", api_key);
        if (reply.code == 200) {
            approved++;
            log(Level::Info, "Approved account " + std::to_string(id));
        } else if (reply.code == 403) {
            refused++;
            log(Level::Warn, "The backend refused account " + std::to_string(id));
        } else if (reply.code == 409) {
            already_reviewed++;
            log(Level::Debug, "Account " + std::to_string(id) + " was already reviewed");
        } else if (reply.code == 401) {
            log(Level::Error, "The backend rejected the API key, the cycle stops");
            return;
        } else {
            failed++;
            log(Level::Error, "The backend responded " + std::to_string(reply.code) + " for account " + std::to_string(id));
        }
    }
    log(Level::Info, "Cycle finished. Approved " + std::to_string(approved) + ", left for the administrators " +
                         std::to_string(skipped) + ", refused " + std::to_string(refused) + ", already reviewed " +
                         std::to_string(already_reviewed) + ", failed " + std::to_string(failed));
}

int main() {
    signal(SIGTERM, handle_signal);
    signal(SIGINT, handle_signal);

    const char* backend_env = getenv("BACKEND_URL");
    const char* key_env = getenv("WORKER_API_KEY");
    const char* interval_env = getenv("WORKER_INTERVAL_SECONDS");
    std::string backend_url = backend_env ? backend_env : "http://backend:8000";
    int interval = interval_env ? atoi(interval_env) : 60;

    // An unknown LOG_LEVEL keeps INFO and is reported once the log is ready.
    const char* level_env = getenv("LOG_LEVEL");
    const bool level_is_valid = read_level(level_env, &minimum_level);
    if (!level_is_valid) log(Level::Warn, std::string("LOG_LEVEL has an unknown value, INFO is used"));
    if (interval < 1) {
        log(Level::Warn, "WORKER_INTERVAL_SECONDS is not valid, 60 s is used");
        interval = 60;
    }

    // The key has no default value, so a missing one stops the robot.
    if (!key_env || !*key_env) {
        log(Level::Error, "WORKER_API_KEY is not set");
        return 1;
    }
    std::string api_key = key_env;

    curl_global_init(CURL_GLOBAL_DEFAULT);
    log(Level::Info, "Started. Interval: " + std::to_string(interval) + " s");

    while (!stop_requested) {
        run_cycle(backend_url, api_key);
        for (int i = 0; i < interval * 5 && !stop_requested; i++) {
            usleep(200000);
        }
    }

    curl_global_cleanup();
    log(Level::Info, "Stopped");
    return 0;
}
