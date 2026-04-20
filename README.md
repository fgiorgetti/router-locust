# Description

This Project runs HTTP load test through the Skupper Router using Locust.

It has three HTTP services, each one listening on a different port.
The services are:
  - service-a: listens on 127.0.0.1:9191
  - service-b: listens on 127.0.0.1:9292
  - service-c: listens on 127.0.0.1:9393

The router configuration basically routes the following ports (on the left) to the respective services above:
  - 8181 -> 9191 (service-a)
  - 8282 -> 9292 (service-b)
  - 8383 -> 9393 (service-c)

We use locust (http://locust.io/) to load test them. There are two locust scripts here:
  - `locustfile.py` which uses the router ports (8181, 8282, 8383)
  - `locustfile-direct.py` which uses the service ports directly (9191, 9292, 9393)
 
# Running

To run the Services and the Router (as a container), use:

```sh
make start-all
```


# Monitoring the state

Before running the tests, on a separate terminal, run:

```sh
make monitor
```

It will monitor the following stats:
- Netstat info:
  - Connections to the service (direct or from the router)
  - Connections to the router
  - Close Wait to the Service
  - Close Wait to the Router
- SKSTAT info (simply counting lines - value of 1 usually means timeout):
  - skstat -c
  - skstat -l

# Running the load test

There are 4 templates for running the load tests.
Here is how to run each of them and what each one does differently:

## 10 clients for 2 minutes directly on the services (no router in the path)

```sh
make client-direct-low
```

## 10 clients for 2 minutes through the router

```sh
make client-router-low
```

## 500 clients for 2 minutes directly on the services (no router in the path)

```sh
make client-direct
```

## 500 clients for 2 minutes through the router

```sh
make client-router
```

# Observation

If you run only the `client-router-low` template, you'll see that the number of records returned
by `skstat -c` and `skstat -l` will be the same before and after the load test.

But if you run the `client-router` template, you can see that after around 400 client connections opened,
the number of connections from the router to the service starts dropping, till it reaches 0.
After awhile, skstat stops responding and will continue to timeout until all client connections from the
load test are closed.
Once that happens, skstat is responsive again, but the records returned by `skstat -c` and `skstat -l` are different.
We can also see that number of Netstat connections in CLOSE_WAIT remains high.

If you continue to run `client-router` template another one or two times, the router will reach a point when it
becomes irresponsive, even after all client connections are closed, not recovering.

No error indication can be found in the router logs.
