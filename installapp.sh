#!/bin/sh
docker build ./mdcproject/
docker compose create
docker compose start
