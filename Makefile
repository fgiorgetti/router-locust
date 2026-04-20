start-all: start-services start-router-container
stop-all: stop-router-container stop-services 

start-all-binary: start-services start-router-binary
stop-all-binary: stop-router-binary stop-services 

monitor:
	watch -n 1 ./monitor.sh

stop-services:
	@pgrep -f 'python server.py \-\-service ' | xargs -r kill -9
	rm -f service-[abc].log
	@echo Stopped services

stop-router-binary:
	@pgrep -f 'topology\-1/skrouterd-binary.json' | xargs -r kill -9
	rm -f router.log
	@echo Stopped router

start-router-binary:
	skrouterd -c topology-1/skrouterd-binary.json &

stop-router-container:
	podman rm -f router-locust

start-router-container:
	podman run --rm --name router-locust --network host -d -v ./topology-1/skrouterd-container.json:/tmp/skrouterd.json -e CONFIG_FILE=/etc/skupper-router/skrouterd.json quay.io/skupper/skupper-router:main skrouterd -c /tmp/skrouterd.json

start-services:
	pip install -r requirements.txt
	python server.py --service a --port 9191 > service-a.log 2>&1 &
	python server.py --service b --port 9292 > service-b.log 2>&1 &
	python server.py --service c --port 9393 > service-c.log 2>&1 &

_client_low:
	locust \
		--headless \
		--users 10 \
		--spawn-rate 1 \
		--run-time 2m \
		-f $(LOCUSTFILE)

_client:
	locust \
		--headless \
		--users 500 \
		--spawn-rate 5 \
		--run-time 2m \
		-f $(LOCUSTFILE)

client-router: LOCUSTFILE=locustfile.py
client-router: _client

client-router-low: LOCUSTFILE=locustfile.py
client-router-low: _client_low

client-direct: LOCUSTFILE=locustfile-direct.py
client-direct: _client

client-direct-low: LOCUSTFILE=locustfile-direct.py
client-direct-low: _client_low
