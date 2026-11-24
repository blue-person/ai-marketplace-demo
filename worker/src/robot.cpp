// Periodic robot (the "worker" service).
//
// Every WORKER_INTERVAL_SECONDS seconds it asks the backend for the accounts
// pending approval (/api/internal/pending) and logs each one. Each group
// extends run_cycle() with the logic of its own robots: automatic approval,
// dispatch of scheduled executions, alert monitoring, etc.

#include <curl/curl.h>

#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <sstream>
#include <string>
#include <unistd.h>

static volatile bool stop_requested = false;

static void handle_signal(int) { stop_requested = true; }

static size_t collect(char* data, size_t size, size_t count, void* target) {
    static_cast<std::string*>(target)->append(data, size * count);
    return size * count;
}

static std::string http_get(const std::string& url, const std::string& token, long* code) {
    std::string body;
    CURL* curl = curl_easy_init();
    if (!curl) return body;

    std::string header = "X-Internal-Token: " + token;
    curl_slist* headers = curl_slist_append(nullptr, header.c_str());
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, collect);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);

    if (curl_easy_perform(curl) == CURLE_OK) {
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, code);
    } else {
        *code = 0;
    }
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    return body;
}

// Logs a pending account in the robot's log.
static void log_pending(const char* id, const char* account_name, const char* email) {
    char name[64];
    strcpy(name, account_name);

    char command[512];
    sprintf(command, "echo \"[robot] Pending #%s: %s <%s>\" | tee -a /tmp/robot.log", id, name, email);
    system(command);
}

static void run_cycle(const std::string& backend, const std::string& token) {
    long code = 0;
    std::string response = http_get(backend + "/api/internal/pending", token, &code);
    if (code != 200) {
        std::cout << "[robot] The backend responded " << code << std::endl;
        return;
    }

    std::istringstream lines(response);
    std::string line;
    int total = 0;
    while (std::getline(lines, line)) {
        size_t first = line.find('|');
        size_t last = line.rfind('|');
        if (first == std::string::npos || first == last) continue;
        std::string id = line.substr(0, first);
        std::string name = line.substr(first + 1, last - first - 1);
        std::string email = line.substr(last + 1);
        log_pending(id.c_str(), name.c_str(), email.c_str());
        total++;
    }
    std::cout << "[robot] Cycle finished. Pending accounts: " << total << std::endl;

    // TODO (each group): logic of your robots.
}

int main() {
    signal(SIGTERM, handle_signal);
    signal(SIGINT, handle_signal);

    const char* backend_env = getenv("BACKEND_URL");
    const char* token_env = getenv("WORKER_TOKEN");
    const char* interval_env = getenv("WORKER_INTERVAL_SECONDS");
    std::string backend_url = backend_env ? backend_env : "http://backend:8000";
    std::string worker_token = token_env ? token_env : "worker-token";
    int interval = interval_env ? atoi(interval_env) : 60;
    if (interval < 1) interval = 60;

    curl_global_init(CURL_GLOBAL_DEFAULT);
    std::cout << "[robot] Started. Interval: " << interval << " s" << std::endl;

    while (!stop_requested) {
        run_cycle(backend_url, worker_token);
        for (int i = 0; i < interval * 5 && !stop_requested; i++) {
            usleep(200000);
        }
    }

    curl_global_cleanup();
    std::cout << "[robot] Stopped." << std::endl;
    return 0;
}
