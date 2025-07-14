# Tile Proxy: FastAPI Slippy Map Tile Proxy

A lightweight, production-ready FastAPI server that proxies XYZ (Slippy Map) tile requests to a GeoServer WMS backend. 

Designed for serving raster tiles (e.g., from GeoTIFFs) to web mapping clients like Leaflet, OpenLayers, or MapLibre.

In my setup this instance is setup behind a nginx reverse proxy, sounds excesive I know proxy -> proxy -> GeoServer

## Features
- Converts XYZ tile requests to WMS GetMap requests
- Streams PNG tiles from GeoServer
- In-memory LRU caching for performance
- Configurable via `.env` file
- CORS enabled (for web clients)
- Health check endpoint (`/health`)

## Requirements
- Python 3.10+
- GeoServer with WMS enabled and published layers
- requirements.txt 

## Setup

1. **Clone the repository**
2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
3. **Create a `.env` file** in the project root:
   ```ini
   GEOSERVER_URL=http://192.168.0.28:8080/geoserver/intrade/wms
   CACHE_SIZE=10000
   TILE_SIZE=256
   DEBUG=True
   ```
4. **Run the server (development):**
   ```sh
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

## Production Deployment
- **Recommended:**
  ```sh
  uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
  # or with Gunicorn:
  gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 4
  ```
- Use `nohup`, `tmux`, or `systemd` to keep the server running after logout (see below).
- Place Nginx or Caddy in front for SSL, compression, and security.

## Health Check
- `GET /health` returns `{ "status": "ok" }` for monitoring.

## CORS
- All origins, methods, and headers are allowed by default (suitable for web map clients).

## Example Usage (Leaflet)
```js
L.tileLayer('http://your-server:8000/tiles/intrade:your_layer/{z}/{x}/{y}.png', {
    tileSize: 256,
    maxZoom: 22,
    attribution: 'Tiles © GeoServer'
}).addTo(map);
```

## Environment Variables (.env)
| Variable       | Description                        | Default                                  |
|---------------|------------------------------------|------------------------------------------|
| GEOSERVER_URL | GeoServer WMS endpoint             | http://localhost:8080/geoserver/wms      |
| CACHE_SIZE    | In-memory tile cache size          | 10000                                    |
| TILE_SIZE     | Tile size in pixels                | 256                                      |
| DEBUG         | Enable verbose logging             | True                                     |

## Keeping the Server Running
- **nohup:**
  ```sh
  nohup uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 > server.log 2>&1 &
  disown
  ```

- **systemd:** (recommended for production)
  See the project documentation or ask for a sample service file.

## Troubleshooting
- Check logs for full WMS request URLs and errors.
- Ensure your GeoServer layer names and SRS match your requests.
- If tiles are blank, verify your GeoTIFF covers the requested BBOX.