// Periodic robot (the "worker" service).
//
// Every WORKER_INTERVAL_SECONDS seconds it asks the backend to approve the
// pending accounts that have a complete profile. The backend decides which
// accounts qualify, so the robot only sends the request and logs the answer.

#include <curl/curl.h>

#include <csignal>
#include <cstdlib>
#include <iostream>
#include <string>
#include <unistd.h>

static volatile sig_atomic_t stop_requested = 0;

static void handle_signal(int) { stop_requested = 1; }

static size_t collect(char* data, size_t size, size_t count, void* target) {
    static_cast<std::string*>(target)->append(data, size * count);
    return size * count;
}

// Sends an empty POST with the worker token and returns the body of the answer.
static std::string http_post(const std::string& url, const std::string& token, long* code) {
    std::string body;
    *code = 0;
    CURL* curl = curl_easy_init();
    if (!curl) return body;

    std::string header = "X-Internal-Token: " + token;
    curl_slist* headers = curl_slist_append(nullptr, header.c_str());
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POST, 1L);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, "");
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, collect);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);

    if (curl_easy_perform(curl) == CURLE_OK) {
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, code);
    }
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    return body;
}

static void run_cycle(const std::string& backend, const std::string& token) {
    long code = 0;
    std::string response = http_post(backend + "/api/internal/auto-approve", token, &code);
    if (code != 200) {
        std::cout << "[robot] The backend responded " << code << std::endl;
        return;
    }
    std::cout << "[robot] Cycle finished. Approved accounts: " << response;
    std::cout.flush();
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
