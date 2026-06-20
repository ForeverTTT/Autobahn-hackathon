import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet-polylineoffset";
import {
  formatHourRange,
  getDefaultDateKey,
  getHourlyStatus,
  HOURS,
  ROAD_DIRECTIONS,
  statusLabel as getStatusLabel,
  TRAFFIC_LEVELS,
} from "../lib/trafficData";

const ROUTE_SEGMENTS = [
  {
    road: "A8",
    title: "Munich — Irschenberg",
    path: [
      [48.102985, 11.613309],
      [48.099703, 11.613585],
      [48.082693, 11.618078],
      [48.080532, 11.619202],
      [48.07831, 11.620895],
      [48.055871, 11.64247],
      [48.053634, 11.644206],
      [48.019704, 11.661283],
      [47.993021, 11.679349],
      [47.988857, 11.681251],
      [47.964563, 11.68811],
      [47.959701, 11.689894],
      [47.95501, 11.69244],
      [47.929939, 11.70863],
      [47.900576, 11.720603],
      [47.897391, 11.722667],
      [47.894947, 11.725096],
      [47.89261, 11.728362],
      [47.890753, 11.732118],
      [47.865908, 11.794052],
      [47.864937, 11.798721],
      [47.864597, 11.802473],
      [47.864617, 11.806272],
      [47.865553, 11.816478],
      [47.865384, 11.821719],
      [47.864375, 11.829177],
      [47.862254, 11.838404],
      [47.861624, 11.844408],
      [47.860757, 11.847438],
      [47.856896, 11.856588],
      [47.854711, 11.859999],
      [47.850389, 11.864567],
      [47.848127, 11.866103],
      [47.843195, 11.868409],
      [47.838404, 11.873118],
      [47.828442, 11.891701],
      [47.827966, 11.893864],
      [47.827964, 11.896551],
      [47.830289, 11.905044],
      [47.830254, 11.91008],
      [47.829209, 11.91345],
      [47.822959, 11.925368],
      [47.822194, 11.928138],
      [47.821968, 11.930531],
      [47.822107, 11.932905],
      [47.822769, 11.935712],
      [47.826237, 11.942252],
      [47.827152, 11.946247],
    ],
  },
  {
    road: "A8",
    title: "Irschenberg — AD Inntal",
    path: [
      [47.827152, 11.946247],
      [47.827089, 11.949446],
      [47.825852, 11.958643],
      [47.822698, 11.966649],
      [47.821758, 11.970965],
      [47.821833, 11.990755],
      [47.820116, 12.016813],
      [47.817883, 12.028939],
      [47.816562, 12.048569],
      [47.814753, 12.063341],
      [47.809363, 12.100301],
      [47.807581, 12.119656],
    ],
  },
  {
    road: "A8",
    title: "AD Inntal — Chiemsee",
    path: [
      [47.807581, 12.119656],
      [47.8047, 12.155214],
      [47.802556, 12.170849],
      [47.802144, 12.185814],
      [47.800846, 12.190415],
      [47.798059, 12.194888],
      [47.796943, 12.197309],
      [47.795949, 12.202291],
      [47.795993, 12.205325],
      [47.796749, 12.21128],
      [47.796389, 12.219229],
      [47.798091, 12.232707],
      [47.797949, 12.245395],
      [47.798331, 12.252927],
      [47.799861, 12.262375],
      [47.803473, 12.274552],
      [47.804118, 12.278938],
      [47.804008, 12.294569],
      [47.803319, 12.302219],
      [47.802027, 12.308204],
      [47.801953, 12.311884],
      [47.806166, 12.332201],
      [47.809315, 12.34115],
      [47.812231, 12.353485],
      [47.814606, 12.359446],
      [47.815871, 12.367031],
      [47.817159, 12.371394],
      [47.821663, 12.379718],
      [47.8248, 12.382807],
      [47.830932, 12.387219],
      [47.832491, 12.389555],
      [47.833674, 12.392871],
      [47.834101, 12.396594],
      [47.83337, 12.408269],
      [47.833971, 12.418107],
      [47.833806, 12.436495],
      [47.834633, 12.442444],
      [47.836797, 12.449708],
      [47.837387, 12.452807],
      [47.83877, 12.479682],
      [47.838651, 12.48439],
      [47.838031, 12.488697],
      [47.831172, 12.516667],
      [47.829219, 12.528551],
      [47.82749, 12.546997],
      [47.827274, 12.552745],
      [47.826287, 12.560322],
      [47.826362, 12.565177],
      [47.828379, 12.583907],
      [47.827899, 12.597563],
      [47.828697, 12.609749],
      [47.827525, 12.619643],
      [47.829211, 12.632147],
      [47.828473, 12.642107],
    ],
  },
  {
    road: "A8",
    title: "Chiemsee — Salzburg",
    path: [
      [47.828473, 12.642107],
      [47.825269, 12.654488],
      [47.825461, 12.668413],
      [47.824325, 12.677188],
      [47.824806, 12.68064],
      [47.827479, 12.688842],
      [47.828819, 12.699364],
      [47.829207, 12.709518],
      [47.829172, 12.722881],
      [47.831148, 12.737223],
      [47.830552, 12.743441],
      [47.829614, 12.746405],
      [47.827183, 12.751569],
      [47.826346, 12.755922],
      [47.827135, 12.769196],
      [47.826548, 12.778071],
      [47.826633, 12.782258],
      [47.829189, 12.797526],
      [47.828807, 12.811229],
      [47.828146, 12.813936],
      [47.826302, 12.818818],
      [47.824731, 12.821799],
      [47.819966, 12.827724],
      [47.813044, 12.83389],
      [47.811129, 12.836055],
      [47.796067, 12.860933],
      [47.794038, 12.863556],
      [47.782041, 12.876],
      [47.769863, 12.894772],
      [47.768294, 12.898085],
      [47.766303, 12.905801],
      [47.765956, 12.908857],
      [47.768084, 12.933921],
      [47.768953, 12.966805],
      [47.770614, 12.976311],
      [47.77044, 12.979205],
      [47.769726, 12.98239],
    ],
  },
  {
    road: "A93",
    title: "AD Inntal — Brannenburg",
    path: [
      [47.807678, 12.119865],
      [47.809298, 12.101951],
      [47.810372, 12.094035],
      [47.810912, 12.093241],
      [47.81144, 12.093544],
      [47.81153, 12.094472],
      [47.811103, 12.095845],
      [47.810424, 12.096571],
      [47.809584, 12.096773],
      [47.808506, 12.096282],
      [47.803986, 12.09204],
      [47.800695, 12.090264],
      [47.797948, 12.089785],
      [47.79159, 12.090121],
      [47.787102, 12.090781],
      [47.781236, 12.09244],
      [47.775271, 12.09512],
      [47.769842, 12.098453],
      [47.763996, 12.103255],
      [47.749821, 12.117781],
      [47.739594, 12.126625],
    ],
  },
  {
    road: "A93",
    title: "Brannenburg — Oberaudorf",
    path: [
      [47.739594, 12.126625],
      [47.723518, 12.138933],
      [47.702306, 12.159092],
      [47.700056, 12.160501],
      [47.697281, 12.161675],
      [47.686149, 12.164221],
      [47.681204, 12.166446],
      [47.676145, 12.17051],
      [47.66801, 12.180687],
      [47.66524, 12.182367],
      [47.66095, 12.183338],
    ],
  },
  {
    road: "A93",
    title: "Oberaudorf — Kiefersfelden",
    path: [
      [47.66095, 12.183338],
      [47.65745, 12.184165],
      [47.653654, 12.185826],
      [47.642069, 12.191992],
      [47.628868, 12.200047],
      [47.623207, 12.201734],
      [47.618073, 12.202362],
      [47.615365, 12.202331],
      [47.612976, 12.201672],
      [47.610559, 12.200331],
      [47.60844, 12.198443],
      [47.606374, 12.19573],
      [47.603915, 12.190965],
      [47.601136, 12.183095],
      [47.598655, 12.178296],
      [47.598249, 12.176169],
    ],
  },
];

function statusColor(status) {
  return TRAFFIC_LEVELS[status]?.color ?? TRAFFIC_LEVELS.smooth.color;
}

function OpenStreetMap({
  selectedRoad,
  selectedDirection,
  selectedDate,
  selectedHour,
}) {
  const mapElement = useRef(null);
  const mapInstance = useRef(null);
  const routeLayers = useRef(null);

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
      segment.path.forEach((point) => bounds.extend(point));
    });

    map.fitBounds(bounds, {
      paddingTopLeft: [50, 50],
      paddingBottomRight: [50, 50],
    });

    routeLayers.current = L.layerGroup().addTo(map);
    mapInstance.current = map;
    setTimeout(() => map.invalidateSize(), 0);

    return () => {
      mapInstance.current = null;
      routeLayers.current = null;
      map.remove();
    };
  }, []);

  useEffect(() => {
    const map = mapInstance.current;
    const layerGroup = routeLayers.current;
    if (!map || !layerGroup) return;

    layerGroup.clearLayers();

    const visibleSegments = ROUTE_SEGMENTS.filter(
      (segment) => selectedRoad === "all" || segment.road === selectedRoad,
    );

    visibleSegments.forEach((segment) => {
      const latLngs = segment.path;
      const segmentIndex = ROUTE_SEGMENTS.indexOf(segment);

      const directionLines = [
        {
          label: ROAD_DIRECTIONS[segment.road][0],
          offset: -4,
          number: 1,
        },
        {
          label: ROAD_DIRECTIONS[segment.road][1],
          offset: 4,
          number: 2,
        },
      ].filter(
        (direction) =>
          selectedDirection === "both" ||
          direction.number === selectedDirection,
      );

      directionLines.forEach((direction) => {
        const offset =
          selectedDirection === "both" ? direction.offset : 0;
        const status = getHourlyStatus(
          selectedDate,
          segment.road,
          direction.number,
          selectedHour,
          segmentIndex,
        );

        L.polyline(latLngs, {
          color: "#ffffff",
          weight: 8,
          opacity: 0.98,
          offset,
          interactive: false,
          lineCap: "round",
          lineJoin: "round",
        }).addTo(layerGroup);

        const line = L.polyline(latLngs, {
          color: statusColor(status),
          weight: 5,
          opacity: 1,
          offset,
          lineCap: "round",
          lineJoin: "round",
        }).addTo(layerGroup);

        const statusText = `${getStatusLabel(status)} traffic`;

        line.bindTooltip(
          `
            <div class="leaflet-road-popup">
              <div>
                <span class="map-route-badge">${segment.road}</span>
                <span class="direction-number">Direction ${direction.number}</span>
                <span class="map-status ${status}">${statusText}</span>
              </div>
              <strong>${direction.label}</strong>
              <small>${segment.title} · ${selectedDate} · ${formatHourRange(selectedHour)}</small>
            </div>
          `,
          {
            className: "road-tooltip",
            direction: "top",
            sticky: true,
            opacity: 1,
          },
        );

        line.on("mouseover", () => line.setStyle({ weight: 7 }));
        line.on("mouseout", () => line.setStyle({ weight: 5 }));
      });
    });
  }, [selectedDate, selectedDirection, selectedHour, selectedRoad]);

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

function initialMapState() {
  const query = window.location.hash.split("?")[1] ?? "";
  const params = new URLSearchParams(query);
  const roadParam = params.get("road");
  const directionParam = Number(params.get("direction"));
  const hourParam = Number(params.get("hour"));
  const dateParam = params.get("date");
  const validDate = /^\d{4}-\d{2}-\d{2}$/.test(dateParam ?? "");
  const dateYear = validDate ? Number(dateParam.slice(0, 4)) : 0;
  const road = roadParam === "A8" || roadParam === "A93" ? roadParam : "all";

  return {
    road,
    direction:
      road !== "all" && (directionParam === 1 || directionParam === 2)
        ? directionParam
        : "both",
    date:
      validDate && dateYear >= 2023 && dateYear <= 2029
        ? dateParam
        : getDefaultDateKey(),
    hour: hourParam >= 0 && hourParam <= 23 ? hourParam : 8,
  };
}

export default function MapPage() {
  const initialState = useRef(initialMapState());
  const [selectedRoad, setSelectedRoad] = useState(initialState.current.road);
  const [selectedDirection, setSelectedDirection] = useState(
    initialState.current.direction,
  );
  const [selectedDate, setSelectedDate] = useState(initialState.current.date);
  const [selectedHour, setSelectedHour] = useState(initialState.current.hour);
  const selectedRoadDirections =
    selectedRoad === "all" ? null : ROAD_DIRECTIONS[selectedRoad];

  const pageRef = useRef(null);
  const toolbarRef = useRef(null);

  const selectRoad = (road) => {
    setSelectedRoad(road);
    setSelectedDirection("both");
  };

  // expose the top toolbar height so the map can fill exactly below it
  useEffect(() => {
    const measure = () => {
      const barH = toolbarRef.current?.offsetHeight ?? 56;
      pageRef.current?.style.setProperty("--bar-h", `${barH}px`);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [selectedRoad]);

  useEffect(() => {
    const params = new URLSearchParams({
      date: selectedDate,
      hour: String(selectedHour),
      road: selectedRoad,
      direction: String(selectedDirection),
    });
    window.history.replaceState(null, "", `#/map?${params.toString()}`);
  }, [selectedDate, selectedDirection, selectedHour, selectedRoad]);

  return (
    <section className="map-fullpage" ref={pageRef}>
      <div className="map-toolbar" ref={toolbarRef}>
        <span className="panel-kicker">LIVE CORRIDOR</span>
        <label className="map-control">
          <span>Date</span>
          <input
            type="date"
            min="2023-01-01"
            max="2029-12-31"
            value={selectedDate}
            onChange={(event) => {
              if (event.target.value) setSelectedDate(event.target.value);
            }}
          />
        </label>
        <label className="map-control">
          <span>Hour</span>
          <select
            value={selectedHour}
            onChange={(event) => setSelectedHour(Number(event.target.value))}
          >
            {HOURS.map((hour) => (
              <option value={hour} key={hour}>
                {formatHourRange(hour)}
              </option>
            ))}
          </select>
        </label>
        <div className="map-toolbar-group">
          <span className="map-filter-label">Highway</span>
          <div className="map-pills">
            {[
              ["all", "All"],
              ["A8", "A8"],
              ["A93", "A93"],
            ].map(([value, label]) => (
              <button
                className={selectedRoad === value ? "active" : ""}
                type="button"
                key={value}
                onClick={() => selectRoad(value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        {selectedRoadDirections && (
          <div className="map-toolbar-group map-toolbar-dir">
            <span className="map-filter-label">Direction</span>
            <div className="map-dir-pills">
              <button
                className={selectedDirection === "both" ? "active" : ""}
                type="button"
                onClick={() => setSelectedDirection("both")}
              >
                Both
              </button>
              {selectedRoadDirections.map((direction, index) => (
                <button
                  className={selectedDirection === index + 1 ? "active" : ""}
                  type="button"
                  key={direction}
                  onClick={() => setSelectedDirection(index + 1)}
                >
                  {direction}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="map-fill">
        <OpenStreetMap
          selectedRoad={selectedRoad}
          selectedDirection={selectedDirection}
          selectedDate={selectedDate}
          selectedHour={selectedHour}
        />
      </div>
    </section>
  );
}
