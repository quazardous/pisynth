# Developer shortcuts (#2415). The Pi side is still ./deploy.sh; these run on the laptop.
COMPOSE = DEV_UID=$$(id -u) DEV_GID=$$(id -g) docker compose -f dev/docker-compose.yml

.PHONY: help dev dev-pi down logs pair pair-built stats test lint build tunnel shell

help:  ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

dev:  ## web companion stack, simulated MIDI (https://<LAN IP>:15173, then `make pair`)
	$(COMPOSE) up -d --build && $(COMPOSE) ps

dev-pi:  ## same, MIDI bridged from the Pi's real keyboard over SSH (PISYNTH_HOST / pisynth.conf)
	@. ./pisynth.conf 2>/dev/null; MIDI_SOURCE=pi PISYNTH_HOST=$${PISYNTH_HOST:?set PISYNTH_HOST} $(COMPOSE) up -d --build --force-recreate web app && $(COMPOSE) ps

down:  ## stop the stack
	$(COMPOSE) down

logs:  ## follow both containers' logs
	$(COMPOSE) logs -f --tail=50

pair:  ## print a one-time pairing URL + QR for the phone (Vite dev server)
	$(COMPOSE) exec -e APP=$${APP_PORT:-15173} -e LAN_IP=$$(ip -4 route get 192.0.2.1 | awk '{for(i=1;i<=NF;i++) if($$i=="src") print $$(i+1)}') web python3 dev/pair.py

pair-built:  ## same, but for the built app served by pisynth-web itself (host :18443)
	$(COMPOSE) exec -e APP=$${WEB_PORT:-18443} -e LAN_IP=$$(ip -4 route get 192.0.2.1 | awk '{for(i=1;i<=NF;i++) if($$i=="src") print $$(i+1)}') web python3 dev/pair.py

stats:  ## relay latency / clients / frames from the running server
	@curl -fsS http://127.0.0.1:9811/admin/stats && echo

test:  ## pytest (Python + the browser logic under Node)
	uvx --with numpy,pillow,pyyaml pytest

lint:  ## ruff
	uvx ruff check ui tools tests web dev

build:  ## build the Svelte app into web/static (commit the result)
	cd web/app && ([ -d node_modules ] || npm ci) && npm run build

tunnel:  ## forward the companion running ON the Pi to localhost
	dev/tunnel.sh

shell:  ## a shell in the web container
	$(COMPOSE) exec web bash
