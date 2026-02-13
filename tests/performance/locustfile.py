from locust import HttpUser, between, task


class SystemUser(HttpUser):
    wait_time = between(1, 2)

    @task(3)
    def check_health(self):
        self.client.get("/health")

    @task(1)
    def check_metrics(self):
        self.client.get("/metrics")

    @task(1)
    def check_system_info(self):
        # Assuming we can mock authentication or bypass it locally
        # For now, we expect 403 or 401 if not authenticated, which is still a valid load test for the server
        self.client.get("/api/v1/system/info")
