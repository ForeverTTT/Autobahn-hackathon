import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { loadGoogleMaps } from "../lib/googleMaps";

const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

const ROUTE_SEGMENTS = [
  {
    road: "A8",
    title: "Munich — Irschenberg",
    status: "smooth",
    path: [
      { lat: 48.137, lng: 11.576 },
      { lat: 48.092, lng: 11.78 },
      { lat: 47.835, lng: 11.918 },
    ],
  },
  {
    road: "A8",
    title: "Irschenberg — Rosenheim",
    status: "heavy",
    path: [
      { lat: 47.835, lng: 11.918 },
      { lat: 47.856, lng: 12.118 },
    ],
  },
  {
    road: "A8",
    title: "Rosenheim — Chiemsee",
    status: "smooth",
    path: [
      { lat: 47.856, lng: 12.118 },
      { lat: 47.813, lng: 12.375 },
      { lat: 47.866, lng: 12.64 },
    ],
  },
  {
    road: "A8",
    title: "Chiemsee — Salzburg",
    status: "heavy",
    path: [
      { lat: 47.866, lng: 12.64 },
      { lat: 47.81, lng: 13.055 },
    ],
  },
  {
    road: "A93",
    title: "AD Inntal — Brannenburg",
    status: "smooth",
    path: [
      { lat: 47.827, lng: 12.128 },
      { lat: 47.739, lng: 12.09 },
    ],
  },
  {
    road: "A93",
    title: "Brannenburg — Oberaudorf",
    status: "heavy",
    path: [
      { lat: 47.739, lng: 12.09 },
      { lat: 47.65, lng: 12.17 },
    ],
  },
  {
    road: "A93",
    title: "Oberaudorf — Kufstein",
    status: "smooth",
    path: [
      { lat: 47.65, lng: 12.17 },
      { lat: 47.595, lng: 12.18 },
    ],
  },
];

const MAP_STYLES = [
  { elementType: "geometry", stylers: [{ color: "#eef0e9" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#5b625b" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#f7f8f4" }] },
  {
    featureType: "administrative",
    elementType: "geometry.stroke",
    stylers: [{ color: "#cfd4ca" }],
  },
  {
    featureType: "landscape.natural",
    elementType: "geometry",
    stylers: [{ color: "#e7ece1" }],
  },
  {
    featureType: "poi",
    elementType: "geometry",
    stylers: [{ color: "#e0e7db" }],
  },
  {
    featureType: "poi",
    elementType: "labels.text.fill",
    stylers: [{ color: "#687165" }],
  },
  {
    featureType: "road",
    elementType: "geometry",
    stylers: [{ color: "#ffffff" }],
  },
  {
    featureType: "road",
    elementType: "geometry.stroke",
    stylers: [{ color: "#d9ddd4" }],
  },
  {
    featureType: "road.highway",
    elementType: "geometry",
    stylers: [{ color: "#d5d9cf" }],
  },
  {
    featureType: "transit",
    stylers: [{ visibility: "off" }],
  },
  {
    featureType: "water",
    elementType: "geometry",
    stylers: [{ color: "#cddfe0" }],
  },
];

function statusColor(status) {
  return status === "heavy" ? "#ef554a" : "#45aa72";
}

function GoogleMap({ onError }) {
  const mapElement = useRef(null);

  useEffect(() => {
    let disposed = false;
    let infoWindow;
    const polylines = [];

    loadGoogleMaps(GOOGLE_MAPS_API_KEY)
      .then((maps) => {
        if (disposed) return;

        const map = new maps.Map(mapElement.current, {
          center: { lat: 47.88, lng: 12.25 },
          zoom: 9,
          minZoom: 7,
          mapTypeControl: false,
          fullscreenControl: false,
          streetViewControl: false,
          rotateControl: false,
          styles: MAP_STYLES,
          gestureHandling: "greedy",
        });

        infoWindow = new maps.InfoWindow({
          disableAutoPan: true,
          pixelOffset: new maps.Size(0, -8),
        });

        const bounds = new maps.LatLngBounds();

        ROUTE_SEGMENTS.forEach((segment) => {
          segment.path.forEach((point) => bounds.extend(point));

          const polyline = new maps.Polyline({
            path: segment.path,
            geodesic: true,
            strokeColor: statusColor(segment.status),
            strokeOpacity: 1,
            strokeWeight: 9,
            map,
            zIndex: segment.status === "heavy" ? 4 : 3,
          });

          const showInfo = (event) => {
            const statusLabel =
              segment.status === "heavy" ? "Heavy traffic" : "Smooth traffic";
            infoWindow.setPosition(event.latLng);
            infoWindow.setContent(`
              <div class="google-road-popup">
                <div>
                  <span class="google-route-badge">${segment.road}</span>
                  <span class="google-status ${segment.status}">${statusLabel}</span>
                </div>
                <strong>${segment.title}</strong>
                <small>Road segment information</small>
              </div>
            `);
            infoWindow.open({ map });
          };

          polyline.addListener("mouseover", showInfo);
          polyline.addListener("mousemove", showInfo);
          polyline.addListener("mouseout", () => infoWindow.close());
          polylines.push(polyline);
        });

        map.fitBounds(bounds, 48);
      })
      .catch(onError);

    return () => {
      disposed = true;
      polylines.forEach((polyline) => polyline.setMap(null));
      infoWindow?.close();
    };
  }, [onError]);

  return <div className="google-map" ref={mapElement} />;
}

function InteractiveDemoMap() {
  const mapElement = useRef(null);

  useEffect(() => {
    const map = L.map(mapElement.current, {
      center: [47.88, 12.25],
      zoom: 9,
      minZoom: 6,
      maxZoom: 18,
      zoomControl: false,
      scrollWheelZoom: true,
      doubleClickZoom: true,
      dragging: true,
      touchZoom: true,
    });

    L.control.zoom({ position: "topright" }).addTo(map);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    const bounds = L.latLngBounds();

    ROUTE_SEGMENTS.forEach((segment) => {
      const latLngs = segment.path.map((point) => [point.lat, point.lng]);
      latLngs.forEach((point) => bounds.extend(point));

      L.polyline(latLngs, {
        color: "#ffffff",
        weight: 13,
        opacity: 0.95,
        interactive: false,
      }).addTo(map);

      const line = L.polyline(latLngs, {
        color: statusColor(segment.status),
        weight: 8,
        opacity: 1,
        lineCap: "round",
        lineJoin: "round",
      }).addTo(map);

      const statusLabel =
        segment.status === "heavy" ? "Heavy traffic" : "Smooth traffic";

      line.bindTooltip(
        `
          <div class="leaflet-road-popup">
            <div>
              <span class="google-route-badge">${segment.road}</span>
              <span class="google-status ${segment.status}">${statusLabel}</span>
            </div>
            <strong>${segment.title}</strong>
            <small>Road segment information</small>
          </div>
        `,
        {
          className: "road-tooltip",
          direction: "top",
          sticky: true,
          opacity: 1,
        },
      );

      line.on("mouseover", () => line.setStyle({ weight: 11 }));
      line.on("mouseout", () => line.setStyle({ weight: 8 }));
    });

    map.fitBounds(bounds, {
      paddingTopLeft: [330, 70],
      paddingBottomRight: [55, 55],
    });

    return () => map.remove();
  }, []);

  return <div className="leaflet-map" ref={mapElement} />;
}

function LocationIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="2.5" />
    </svg>
  );
}

export default function MapPage() {
  const [mapError, setMapError] = useState(false);
  const showGoogleMap = Boolean(GOOGLE_MAPS_API_KEY) && !mapError;

  return (
    <section className="map-page page-container">
      <div className="page-heading map-heading">
        <div>
          <span className="eyebrow">CORRIDOR VIEW</span>
          <h1>See where traffic slows down.</h1>
          <p>Hover over a colored road segment to inspect its information.</p>
        </div>

        <div className="map-location-chip">
          <LocationIcon />
          <span>
            <small>Region</small>
            <strong>Upper Bavaria · Tyrol</strong>
          </span>
        </div>
      </div>

      <div className="map-card">
        <div className="map-overlay-panel">
          <span className="panel-kicker">LIVE CORRIDORS</span>
          <h2>A8 East & A93 South</h2>
          <p>Move your pointer over either route.</p>

          <div className="map-route-list">
            <div>
              <span className="route-badge a8">A8</span>
              <span>
                <strong>Munich → Salzburg</strong>
                <small>Eastbound corridor</small>
              </span>
            </div>
            <div>
              <span className="route-badge a93">A93</span>
              <span>
                <strong>Rosenheim → Kufstein</strong>
                <small>Southbound corridor</small>
              </span>
            </div>
          </div>

          <div className="map-legend">
            <span>
              <i className="legend-dot smooth" /> Smooth
            </span>
            <span>
              <i className="legend-dot heavy" /> Heavy
            </span>
          </div>
        </div>

        {showGoogleMap ? (
          <GoogleMap onError={() => setMapError(true)} />
        ) : (
          <InteractiveDemoMap />
        )}
      </div>
    </section>
  );
}
