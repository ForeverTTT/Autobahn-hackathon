# AlpineFlow Web

React/Vite demo frontend with:

- Calendar covering every month from 2023 through 2029
- Two deterministic demo traffic indicators per day (A8 and A93)
- Google Maps integration with hoverable road segments
- Interactive OpenStreetMap fallback when no Google API key is configured

## Run

```bash
npm install
npm run dev
```

## Google Maps

Copy `.env.example` to `.env`, add a Google Maps Platform API key, and enable
the **Maps JavaScript API** for that key:

```bash
VITE_GOOGLE_MAPS_API_KEY=your_key_here
```

Restart the Vite dev server after changing the environment file.
