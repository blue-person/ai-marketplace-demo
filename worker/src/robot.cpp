// Include libraries
#include <curl/curl.h>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <csignal>
#include <cstdlib>
#include <iostream>
#include <string>
#include <unistd.h>
#include <vector>

using json = nlohmann::json;

// Constants
static const long APPROVAL_TIMEOUT_SECONDS = 15;
static const long LIST_TIMEOUT_SECONDS = 15;
static const long LAUNCH_TIMEOUT_SECONDS = 25;
static const int MAX_WAIT_SECONDS = 30;
static const int MAX_FAILURES_COUNTED = 10;

// Flag that the signal handler sets to stop the loop
static volatile sig_atomic_t stop_requested = 0;

// Ask the main loop to stop when the container receives a signal
static void handle_signal(int) { stop_requested = 1; }

// Levels of the log from the most detailed to the most serious
enum class Level { Debug, Info, Warn, Error };

// Lowest level that is written
static Level minimum_level = Level::Info;

// Tasks that the same program can do and the variable ROBOT_TASK chooses one
enum class Task { Approvals, Dispatch };

// Write a line when its level reaches the minimum and send warnings and errors to the error output
static void log(Level level, const std::string& message) {
    if (level < minimum_level) return;
    const char* names[] = {"DEBUG", "INFO", "WARN", "ERROR"};
    std::ostream& out = level >= Level::Warn ? std::cerr : std::cout;
    out << "[" << names[static_cast<int>(level)] << "] " << message << std::endl;
}

// Read the minimum level from LOG_LEVEL and return false when the value is not a level
static bool read_level(const char* text, Level* level) {
    const std::string name = text ? text : "INFO";
    if (name == "DEBUG") *level = Level::Debug;
    else if (name == "INFO") *level = Level::Info;
    else if (name == "WARN") *level = Level::Warn;
    else if (name == "ERROR") *level = Level::Error;
    else return false;
    return true;
}

// Read the task from ROBOT_TASK and return false when it is missing or unknown
static bool read_task(const char* text, Task* task) {
    const std::string name = text ? text : "";
    if (name == "approvals") *task = Task::Approvals;
    else if (name == "dispatch") *task = Task::Dispatch;
    else return false;
    return true;
}

// Append the data that curl receives to the string behind the pointer
static size_t collect(char* data, size_t size, size_t count, void* target) {
    static_cast<std::string*>(target)->append(data, size * count);
    return size * count;
}

// Status code and body of an answer where a code of 0 means that no answer arrived
struct Reply {
    long code = 0;
    std::string body;
};

// Send a GET or an empty POST with the API key in the Authorization header
static Reply send_request(const std::string& method, const std::string& url, const std::string& api_key,
                          long timeout_seconds) {
    Reply reply;
    CURL* curl = curl_easy_init();
    if (!curl) return reply;

    std::string header = "Authorization: Bearer " + api_key;
    curl_slist* headers = curl_slist_append(nullptr, header.c_str());
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_PROTOCOLS_STR, "http,https");
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, timeout_seconds);
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

// A field is present when it is a text with at least one character that is not a space
static bool is_present(const json& registration, const char* field) {
    if (!registration.contains(field) || !registration.at(field).is_string()) return false;
    const std::string text = registration.at(field).get<std::string>();
    return text.find_first_not_of(" \t\r\n") != std::string::npos;
}

// The profile is complete when the organization and the country are present
static bool is_profile_complete(const json& registration) {
    return is_present(registration, "organization") && is_present(registration, "country");
}

// Read the list of registrations and return false when the answer cannot be used
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

// Approve the pending registrations with a complete profile and return false when the cycle had a failure
static bool run_approval_cycle(const std::string& backend, const std::string& api_key) {
    json registrations;
    Reply list = send_request("GET", backend + "/api/internal/registrations", api_key, APPROVAL_TIMEOUT_SECONDS);
    if (!read_registrations(list, &registrations)) {
        return false;
    }

    int approved = 0, skipped = 0, refused = 0, already_reviewed = 0, failed = 0;
    for (const json& registration : registrations) {
        if (!registration.is_object() || !registration.contains("id") || !registration.at("id").is_number_integer()) {
            failed++;
            log(Level::Warn, "A registration without a valid id was ignored");
            continue;
        }
        long long id = registration.at("id").get<long long>();

        // The decision is made here and the backend checks it again
        if (!is_profile_complete(registration)) {
            skipped++;
            log(Level::Debug, "Account " + std::to_string(id) + " is left for the administrators");
            continue;
        }
        Reply reply = send_request("POST", backend + "/api/internal/registrations/" + std::to_string(id) + "/approve",
                                   api_key, APPROVAL_TIMEOUT_SECONDS);
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
            return false;
        } else {
            failed++;
            log(Level::Error, "The backend responded " + std::to_string(reply.code) + " for account " + std::to_string(id));
        }
    }
    log(Level::Info, "Cycle finished. Approved " + std::to_string(approved) + ", left for the administrators " +
                         std::to_string(skipped) + ", refused " + std::to_string(refused) + ", already reviewed " +
                         std::to_string(already_reviewed) + ", failed " + std::to_string(failed));
    return failed == 0 && refused == 0;
}

// Read the ids of the due schedules and return false when the answer cannot be used
static bool read_due_schedules(const Reply& reply, std::vector<long long>* ids) {
    if (reply.code != 200) {
        log(Level::Error, "The backend responded " + std::to_string(reply.code) + " to the list of schedules");
        return false;
    }
    json data = json::parse(reply.body, nullptr, false);
    if (data.is_discarded() || !data.is_object() || !data.contains("schedules") || !data.at("schedules").is_array()) {
        log(Level::Error, "The list of schedules has an unexpected format");
        return false;
    }
    for (const json& schedule : data.at("schedules")) {
        if (!schedule.is_object() || !schedule.contains("id") || !schedule.at("id").is_number_integer()) {
            log(Level::Warn, "A schedule without a valid id was ignored");
            continue;
        }
        ids->push_back(schedule.at("id").get<long long>());
    }
    return true;
}

// Read the outcome that the backend reports for a launch and return unknown when it is missing
static std::string read_outcome(const Reply& reply) {
    json data = json::parse(reply.body, nullptr, false);
    if (data.is_discarded() || !data.is_object() || !data.contains("outcome") || !data.at("outcome").is_string()) {
        return "unknown";
    }
    return data.at("outcome").get<std::string>();
}

// Ask the backend to launch each due schedule one after the other and return false when the cycle had a failure
static bool run_dispatch_cycle(const std::string& backend, const std::string& api_key) {
    std::vector<long long> ids;
    Reply list = send_request("GET", backend + "/api/internal/schedules/due", api_key, LIST_TIMEOUT_SECONDS);
    if (!read_due_schedules(list, &ids)) {
        return false;
    }

    int launched = 0, not_due = 0, refused = 0, failed = 0;
    for (long long id : ids) {
        if (stop_requested) break;
        Reply reply = send_request("POST", backend + "/api/internal/schedules/" + std::to_string(id) + "/launch",
                                   api_key, LAUNCH_TIMEOUT_SECONDS);
        if (reply.code == 200) {
            launched++;
            log(Level::Info, "Launched schedule " + std::to_string(id) + " with outcome " + read_outcome(reply));
        } else if (reply.code == 409) {
            not_due++;
            log(Level::Debug, "Schedule " + std::to_string(id) + " was not due any more");
        } else if (reply.code == 403) {
            refused++;
            log(Level::Warn, "The backend refused schedule " + std::to_string(id));
        } else if (reply.code == 401) {
            log(Level::Error, "The backend rejected the API key, the cycle stops");
            return false;
        } else {
            failed++;
            log(Level::Error, "The backend responded " + std::to_string(reply.code) + " for schedule " + std::to_string(id));
        }
    }
    if (!ids.empty()) {
        log(Level::Info, "Cycle finished. Launched " + std::to_string(launched) + ", not due any more " +
                             std::to_string(not_due) + ", refused " + std::to_string(refused) + ", failed " +
                             std::to_string(failed));
    }
    return failed == 0 && refused == 0;
}

// Return the seconds to wait after a cycle, which double with each failure in a row up to a limit
static int wait_seconds(int interval, int failures_in_a_row) {
    const long limit = std::max(MAX_WAIT_SECONDS, interval);
    long wait = interval;
    for (int i = 0; i < failures_in_a_row && wait < limit; i++) {
        wait *= 2;
    }
    return static_cast<int>(std::min(wait, limit));
}

// Read the settings and repeat the task of the robot until a signal stops it
int main() {
    signal(SIGTERM, handle_signal);
    signal(SIGINT, handle_signal);

    const char* backend_env = getenv("BACKEND_URL");
    const char* key_env = getenv("WORKER_API_KEY");
    const char* interval_env = getenv("WORKER_INTERVAL_SECONDS");
    std::string backend_url = backend_env ? backend_env : "http://backend:8000";
    int interval = interval_env ? atoi(interval_env) : 60;

    // An unknown LOG_LEVEL keeps INFO and is reported once the log is ready
    const char* level_env = getenv("LOG_LEVEL");
    const bool level_is_valid = read_level(level_env, &minimum_level);
    if (!level_is_valid) log(Level::Warn, std::string("LOG_LEVEL has an unknown value, INFO is used"));
    if (interval < 1) {
        log(Level::Warn, "WORKER_INTERVAL_SECONDS is not valid, 60 s is used");
        interval = 60;
    }

    // The task has no default value so a missing or unknown one stops the robot
    Task task;
    if (!read_task(getenv("ROBOT_TASK"), &task)) {
        log(Level::Error, "ROBOT_TASK must be approvals or dispatch");
        return 1;
    }

    // The key has no default value so a missing one stops the robot
    if (!key_env || !*key_env) {
        log(Level::Error, "WORKER_API_KEY is not set");
        return 1;
    }
    std::string api_key = key_env;

    curl_global_init(CURL_GLOBAL_DEFAULT);
    log(Level::Info, std::string("Started the ") + (task == Task::Dispatch ? "dispatch" : "approval") +
                         " task. Interval: " + std::to_string(interval) + " s");

    int failures_in_a_row = 0;
    while (!stop_requested) {
        const bool worked = task == Task::Dispatch ? run_dispatch_cycle(backend_url, api_key)
                                                   : run_approval_cycle(backend_url, api_key);
        failures_in_a_row = worked ? 0 : std::min(failures_in_a_row + 1, MAX_FAILURES_COUNTED);
        const int wait = wait_seconds(interval, failures_in_a_row);
        if (failures_in_a_row > 0) {
            log(Level::Warn, "The cycle failed " + std::to_string(failures_in_a_row) + " time(s) in a row, the next one is in " +
                                 std::to_string(wait) + " s");
        }
        for (int i = 0; i < wait * 5 && !stop_requested; i++) {
            usleep(200000);
        }
    }

    curl_global_cleanup();
    log(Level::Info, "Stopped");
    return 0;
}
