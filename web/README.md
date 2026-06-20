# AlpineFlow Web

React/Vite demo frontend with:

- Calendar covering every month from 2023 through 2029
- A8/A93 selector with two directional traffic indicators per day
- Interactive OpenStreetMap with draggable, zoomable road segments
- Hoverable road segment information

## Run

From the project root, start the complete local demo with:

```bash
python run_demo.py
```

This starts the local API and the Vite frontend, then opens the calendar in the
browser. The API serves both calendar traffic data and the multi-turn planning
chat at `/api/chat`. Press `Ctrl+C` to stop both services.
