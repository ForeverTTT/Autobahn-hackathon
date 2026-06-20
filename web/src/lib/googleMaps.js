let googleMapsPromise;

export function loadGoogleMaps(apiKey) {
  if (window.google?.maps) {
    return Promise.resolve(window.google.maps);
  }

  if (googleMapsPromise) {
    return googleMapsPromise;
  }

  googleMapsPromise = new Promise((resolve, reject) => {
    const callbackName = "__alpineFlowGoogleMapsReady";
    const existingScript = document.querySelector(
      'script[data-alpineflow-google-maps="true"]',
    );

    window[callbackName] = () => {
      resolve(window.google.maps);
      delete window[callbackName];
    };

    if (existingScript) return;

    const script = document.createElement("script");
    script.dataset.alpineflowGoogleMaps = "true";
    script.async = true;
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(
      apiKey,
    )}&callback=${callbackName}&v=weekly&loading=async`;
    script.onerror = () => {
      googleMapsPromise = undefined;
      delete window[callbackName];
      reject(new Error("Google Maps could not be loaded."));
    };
    document.head.appendChild(script);
  });

  return googleMapsPromise;
}
