(() => {
  const BACKEND_ORIGIN = window.location.protocol === "file:" ? "http://localhost:8000" : "";
  const MAP_URL = `${BACKEND_ORIGIN}/map_total/西部世界游戏地图.tmx`;
  const LOCATION_DATA_URL = `${BACKEND_ORIGIN}/data/map/locations.yaml`;
  const WS_URL = window.location.protocol === "file:"
    ? "ws://localhost:8000/ws"
    : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws`;

  const slideDurations = [6200, 6500, 8200, 12000];
  const clearTileFlags = (gid) => gid & 0x0fffffff;

  const AGENT_LABELS = {
    dolores: "Dolores Abernathy",
    teddy: "Teddy Flood",
    maeve: "Maeve Millay",
    clementine: "Clementine",
    peter_abernathy: "Peter Abernathy",
    sheriff_pickett: "Sheriff Pickett",
    kissy: "Kissy",
    rebus: "Rebus",
    hector_escaton: "Hector Escaton",
    armistice: "Armistice",
    lawrence: "Lawrence",
    william: "William",
    logan: "Logan",
  };

  const LOCATION_LABELS = {
    sweetwater_saloon: "Mariposa Saloon",
    abernathy_ranch: "Abernathy Ranch",
    sweetwater: "Sweetwater",
    sweetwater_plaza: "Sweetwater Plaza",
    sweetwater_sheriff: "Sheriff's Office",
    sweetwater_post_office: "Post Office",
    sweetwater_train_station: "Train Station",
    sweetwater_hotel: "Sweetwater Hotel",
    sweetwater_hospital: "Town Clinic",
    sweetwater_gunsmith: "Gunsmith",
    sweetwater_tailor: "Tailor",
    sweetwater_general_store: "General Store",
    wilderness: "Wilderness",
    train: "Steam Train",
    river: "River",
    mine: "Abandoned Mine",
    church: "Church",
    desert_bandit_hideout: "Bandit Hideout",
    pariah: "Pariah",
    pariah_casino: "Pariah Casino",
    pariah_fight_pit: "Fight Pit",
    frontier_town: "Frontier Town",
    frontier_outpost: "Frontier Outpost",
    host_room_1: "Host Room",
    host_home_2: "Host Home",
    ranch_farm: "Ranch Farm",
    surface_maintenance_station: "Surface Maintenance",
    backstage_control: "Backstage Control",
    cold_storage: "Cold Storage",
    staff_dormitory: "Staff Dormitory",
    programmer_workspace: "Programmer Workspace",
  };

  const els = {
    enterButton: document.querySelector(".enter-game"),
    homeScreen: document.querySelector(".home-screen"),
    storyIntro: document.querySelector(".story-intro"),
    storySlides: Array.from(document.querySelectorAll(".story-slide")),
    appShell: document.getElementById("appShell"),
    statusLight: document.getElementById("statusLight"),
    statusText: document.getElementById("statusText"),
    tickReadout: document.getElementById("tickReadout"),
    tickButton: document.getElementById("tickButton"),
    rightPanel: document.getElementById("rightPanel"),
    rightPanelToggle: document.getElementById("rightPanelToggle"),
    rightPanelClose: document.getElementById("rightPanelClose"),
    mapStage: document.querySelector(".map-stage"),
    canvas: document.getElementById("mapCanvas"),
    mapLoading: document.getElementById("mapLoading"),
    locationDialog: document.getElementById("locationDialog"),
    locationDialogClose: document.getElementById("locationDialogClose"),
    locationDialogType: document.getElementById("locationDialogType"),
    locationDialogTitle: document.getElementById("locationDialogTitle"),
    locationDialogMeta: document.getElementById("locationDialogMeta"),
    locationDialogPresence: document.getElementById("locationDialogPresence"),
    locationDialogEvents: document.getElementById("locationDialogEvents"),
    agentList: document.getElementById("agentList"),
    agentCount: document.getElementById("agentCount"),
    awakeCount: document.getElementById("awakeCount"),
    guestCount: document.getElementById("guestCount"),
    sceneType: document.getElementById("sceneType"),
    selectionTitle: document.getElementById("selectionTitle"),
    selectionMeta: document.getElementById("selectionMeta"),
    awakeningMeter: document.getElementById("awakeningMeter"),
    conditionText: document.getElementById("conditionText"),
    eventList: document.getElementById("eventList"),
  };

  const ctx = els.canvas.getContext("2d");
  let currentSlide = 0;
  let slideTimer = 0;
  let introCompleting = false;
  let appStarted = false;
  let ws = null;
  let reconnectTimer = 0;
  let tickInFlight = false;
  let backendReady = false;
  let snapshotReady = false;
  let mapReady = false;
  let simulationFinished = false;
  let selectedAgentId = null;
  let selectedLocationId = null;
  let dragState = null;

  const simState = {
    tick: -1,
    agents: {},
    scenes: {},
    locations: [],
    locationById: new Map(),
    locationByName: new Map(),
  };

  const mapState = {
    width: 0,
    height: 0,
    tileWidth: 16,
    tileHeight: 16,
    pixelWidth: 0,
    pixelHeight: 0,
    tilesets: [],
    layers: [],
    surface: null,
  };

  const camera = {
    x: 0,
    y: 0,
    zoom: 1,
    minZoom: 0.2,
    maxZoom: 4,
  };

  function showSlide(index) {
    currentSlide = index;
    els.storySlides.forEach((slide, slideIndex) => {
      const isActive = slideIndex === index;
      slide.classList.toggle("is-active", isActive);
      slide.setAttribute("aria-hidden", String(!isActive));
    });
  }

  function advanceSlide() {
    if (currentSlide >= els.storySlides.length - 1) {
      completeIntro();
      return;
    }

    showSlide(currentSlide + 1);
    slideTimer = window.setTimeout(advanceSlide, slideDurations[currentSlide]);
  }

  function startStory(event) {
    event.preventDefault();
    if (appStarted) return;
    window.clearTimeout(slideTimer);
    els.storyIntro.hidden = false;
    els.homeScreen.classList.add("is-retiring");
    els.storyIntro.classList.add("is-running");
    els.storyIntro.classList.remove("is-complete", "is-exiting");
    showSlide(0);
    slideTimer = window.setTimeout(advanceSlide, slideDurations[0]);
  }

  function advanceFromInput(event) {
    if (els.storyIntro.hidden || introCompleting) return;
    event.preventDefault();
    window.clearTimeout(slideTimer);

    if (currentSlide < els.storySlides.length - 1) {
      advanceSlide();
      return;
    }

    completeIntro();
  }

  function completeIntro() {
    if (introCompleting) return;
    introCompleting = true;
    window.clearTimeout(slideTimer);
    els.storyIntro.classList.add("is-complete", "is-exiting");
    startApp();
    window.setTimeout(() => {
      els.storyIntro.hidden = true;
    }, 1150);
  }

  function startApp() {
    if (appStarted) return;
    appStarted = true;
    els.appShell.hidden = false;
    requestAnimationFrame(() => els.appShell.classList.add("is-live"));
    resizeCanvas();
    connectBackend();
    loadWorldMap().catch((error) => {
      console.error(error);
      setMapLoading("Map unavailable. Start the backend and open http://localhost:8000/frontend/index.html.");
    });
  }

  function setStatus(mode, text) {
    els.statusLight.className = `status-light status-light--${mode}`;
    els.statusText.textContent = text;
  }

  function setMapLoading(text) {
    els.mapLoading.hidden = false;
    els.mapLoading.textContent = text;
  }

  function hideMapLoading() {
    els.mapLoading.hidden = true;
  }

  function updateTickButton() {
    els.tickButton.disabled = !backendReady || !snapshotReady || tickInFlight || simulationFinished;
  }

  function setRightPanelOpen(open) {
    els.rightPanel.hidden = !open;
    els.appShell.classList.toggle("is-right-panel-closed", !open);
    els.rightPanelToggle.textContent = open ? "Hide Intel" : "Show Intel";
    els.rightPanelToggle.setAttribute("aria-expanded", String(open));
    window.requestAnimationFrame(resizeCanvas);
  }

  function connectBackend() {
    window.clearTimeout(reconnectTimer);
    setStatus("pending", "Connecting to backend");

    try {
      ws = new WebSocket(WS_URL);
    } catch (error) {
      console.error(error);
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      backendReady = true;
      setStatus("ready", snapshotReady ? "Backend online" : "Awaiting snapshot");
      updateTickButton();
    };

    ws.onmessage = (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch (error) {
        console.warn("Ignoring non-JSON websocket message", error);
        return;
      }

      if (msg.type === "snapshot" || msg.type === "tick_update") {
        applySimulationPayload(msg.data, msg.tick);
        tickInFlight = false;
        setStatus("ready", msg.type === "snapshot" ? "Snapshot loaded" : "Tick complete");
        updateTickButton();
      } else if (msg.type === "simulation_ready") {
        backendReady = true;
        setStatus("ready", snapshotReady ? "Ready for next tick" : "Backend ready");
        updateTickButton();
      } else if (msg.type === "simulation_finished") {
        tickInFlight = false;
        simulationFinished = true;
        setStatus("ready", "Simulation complete");
        updateTickButton();
      }
    };

    ws.onclose = () => {
      backendReady = false;
      tickInFlight = false;
      setStatus("offline", "Backend offline");
      updateTickButton();
      scheduleReconnect();
    };

    ws.onerror = () => {
      setStatus("offline", "Backend connection failed");
    };
  }

  function scheduleReconnect() {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = window.setTimeout(connectBackend, 1800);
  }

  function sendStartTick() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    tickInFlight = true;
    setStatus("pending", "Tick running");
    updateTickButton();
    ws.send(JSON.stringify({ type: "start_tick" }));
  }

  function applySimulationPayload(data, fallbackTick) {
    const payload = data && data.agents ? data : { agents: data || {}, scenes: {} };
    simState.agents = payload.agents || {};
    simState.scenes = payload.scenes || {};
    simState.tick = Number.isInteger(payload.tick) ? payload.tick : fallbackTick;
    snapshotReady = true;

    els.tickReadout.textContent = simState.tick < 0 ? "Initial" : String(simState.tick);
    if (selectedAgentId && !simState.agents[selectedAgentId]) selectedAgentId = null;
    updateAgentList();
    updateInspector();
    if (!els.locationDialog.hidden && selectedLocationId) renderLocationDialog(selectedLocationId);
    draw();
  }

  async function loadWorldMap() {
    setMapLoading("Loading Westworld map");
    const [locationText, tmxText] = await Promise.all([
      fetchText(LOCATION_DATA_URL),
      fetchText(MAP_URL),
    ]);
    loadLocationsFromYaml(locationText);

    const parser = new DOMParser();
    const doc = parser.parseFromString(tmxText, "application/xml");
    const mapNode = doc.querySelector("map");
    if (!mapNode) throw new Error("Invalid TMX map.");

    mapState.width = parseInt(mapNode.getAttribute("width"), 10);
    mapState.height = parseInt(mapNode.getAttribute("height"), 10);
    mapState.tileWidth = parseInt(mapNode.getAttribute("tilewidth"), 10);
    mapState.tileHeight = parseInt(mapNode.getAttribute("tileheight"), 10);
    mapState.pixelWidth = mapState.width * mapState.tileWidth;
    mapState.pixelHeight = mapState.height * mapState.tileHeight;

    parseZoneObjects(mapNode);
    await loadTilesets(mapNode, parser);
    parseLayers(mapNode);
    renderMapSurface();
    fitMapToStage();
    mapReady = true;
    hideMapLoading();
    updateInspector();
    draw();
  }

  async function fetchText(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Failed to fetch ${url}: ${response.status}`);
    return response.text();
  }

  function loadLocationsFromYaml(text) {
    const locations = [];
    let current = null;

    text.split(/\r?\n/).forEach((line) => {
      const idMatch = line.match(/^\s*-\s+id:\s*(.+?)\s*$/);
      if (idMatch) {
        current = { id: idMatch[1].trim() };
        locations.push(current);
        return;
      }

      if (!current) return;
      const fieldMatch = line.match(/^\s+(name|region|type|active):\s*(.+?)\s*$/);
      if (fieldMatch) {
        const [, key, rawValue] = fieldMatch;
        current[key] = rawValue.trim().replace(/^["']|["']$/g, "");
        return;
      }

      const bboxMatch = line.match(/^\s+bbox:\s*\[(.+?)\]\s*$/);
      if (bboxMatch) {
        current.bbox = bboxMatch[1].split(",").map((item) => parseFloat(item.trim()) || 0);
      }
    });

    locations
      .filter((location) => location.active !== "false")
      .forEach((location) => {
        const bbox = location.bbox || [0, 0, 0, 0];
        const normalized = {
          ...location,
          x: bbox[0] || 0,
          y: bbox[1] || 0,
          width: bbox[2] || 0,
          height: bbox[3] || 0,
        };
        simState.locations.push(normalized);
        simState.locationById.set(normalized.id, normalized);
        if (normalized.name) simState.locationByName.set(normalized.name, normalized);
      });
  }

  function parseZoneObjects(mapNode) {
    const zones = Array.from(mapNode.querySelectorAll("objectgroup"))
      .find((group) => group.getAttribute("name") === "zones");
    if (!zones) return;

    zones.querySelectorAll(":scope > object").forEach((objectNode) => {
      const valueNode = objectNode.querySelector("properties property[value]");
      const zoneName = valueNode ? valueNode.getAttribute("value") : "";
      if (!zoneName) return;

      const meta = simState.locationByName.get(zoneName);
      if (!meta) return;
      const bounds = getObjectBounds(objectNode);
      if (!bounds) return;

      const existing = simState.locationById.get(meta.id);
      if (existing && existing._fromZone) return;

      const merged = {
        ...existing,
        ...meta,
        ...bounds,
        _fromZone: true,
      };
      simState.locationById.set(meta.id, merged);
      simState.locationByName.set(zoneName, merged);
    });

    simState.locations = Array.from(simState.locationById.values());
  }

  function getObjectBounds(objectNode) {
    const originX = parseFloat(objectNode.getAttribute("x")) || 0;
    const originY = parseFloat(objectNode.getAttribute("y")) || 0;
    const width = parseFloat(objectNode.getAttribute("width")) || 0;
    const height = parseFloat(objectNode.getAttribute("height")) || 0;
    const polygon = objectNode.querySelector("polygon");

    if (!polygon) {
      return { x: originX, y: originY, width, height };
    }

    const points = (polygon.getAttribute("points") || "")
      .trim()
      .split(/\s+/)
      .map((pair) => pair.split(",").map(Number))
      .filter((pair) => pair.length === 2 && pair.every(Number.isFinite));

    if (!points.length) return { x: originX, y: originY, width, height };

    const xs = points.map((point) => point[0]);
    const ys = points.map((point) => point[1]);
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const maxX = Math.max(...xs);
    const maxY = Math.max(...ys);
    return {
      x: originX + minX,
      y: originY + minY,
      width: maxX - minX,
      height: maxY - minY,
    };
  }

  async function loadTilesets(mapNode, parser) {
    const nodes = Array.from(mapNode.querySelectorAll(":scope > tileset"));
    const entries = nodes.map((node, index) => ({
      node,
      nextFirstgid: nodes[index + 1] ? parseInt(nodes[index + 1].getAttribute("firstgid"), 10) : null,
    }));

    const tilesets = await Promise.all(entries.map(({ node, nextFirstgid }) => loadTileset(node, nextFirstgid, parser)));
    mapState.tilesets = tilesets
      .filter(Boolean)
      .sort((a, b) => a.firstgid - b.firstgid);
  }

  async function loadTileset(node, nextFirstgid, parser) {
    const firstgid = parseInt(node.getAttribute("firstgid"), 10);
    let tilesetNode = node;
    const source = node.getAttribute("source");

    if (source) {
      const tsxText = await fetchText(tileAssetUrl(source)).catch((error) => {
        console.warn(`Skipping missing tileset ${source}`, error);
        return null;
      });
      if (!tsxText) return null;
      const tsxDoc = parser.parseFromString(tsxText, "application/xml");
      tilesetNode = tsxDoc.querySelector("tileset");
    }

    const imageNode = tilesetNode && tilesetNode.querySelector("image");
    const imageSource = imageNode && imageNode.getAttribute("source");
    if (!imageSource) return null;

    const tileWidth = parseInt(tilesetNode.getAttribute("tilewidth"), 10) || mapState.tileWidth;
    const tileHeight = parseInt(tilesetNode.getAttribute("tileheight"), 10) || mapState.tileHeight;
    const image = await loadImageWithFallbacks(imageSource).catch((error) => {
      console.warn(`Skipping tileset image ${imageSource}`, error);
      return null;
    });
    if (!image) return null;
    const columns = parseInt(tilesetNode.getAttribute("columns"), 10) || Math.max(1, Math.floor(image.width / tileWidth));
    const tilecount = parseInt(tilesetNode.getAttribute("tilecount"), 10)
      || (nextFirstgid ? nextFirstgid - firstgid : columns * Math.floor(image.height / tileHeight));

    return { firstgid, tileWidth, tileHeight, columns, tilecount, image };
  }

  function tileAssetUrl(source) {
    return `${BACKEND_ORIGIN}/map_total/${encodeURI(source)}`;
  }

  function imageFallbackSources(source) {
    const sources = [source];
    if (!/\.\.[^.]+$/.test(source)) {
      sources.push(source.replace(/(\.[^.]+)$/, ".$1"));
    }
    return Array.from(new Set(sources));
  }

  async function loadImageWithFallbacks(source) {
    let lastError = null;
    for (const candidate of imageFallbackSources(source)) {
      try {
        return await loadImage(tileAssetUrl(candidate));
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError || new Error(`Image not found: ${source}`);
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.crossOrigin = "anonymous";
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error(`Failed to load image ${url}`));
      image.src = url;
    });
  }

  function parseLayers(mapNode) {
    const layers = [];

    function visit(node, parentVisible = true) {
      Array.from(node.children).forEach((child) => {
        const tagName = child.tagName.toLowerCase();
        const visible = parentVisible && child.getAttribute("visible") !== "0";
        if (tagName === "group") {
          visit(child, visible);
        } else if (tagName === "layer" && visible) {
          const dataNode = child.querySelector("data[encoding='csv']");
          if (!dataNode) return;
          const gids = dataNode.textContent
            .split(",")
            .map((item) => clearTileFlags(parseInt(item.trim(), 10) || 0));
          layers.push({ name: child.getAttribute("name") || "", gids });
        }
      });
    }

    visit(mapNode);
    mapState.layers = layers;
  }

  function renderMapSurface() {
    const surface = document.createElement("canvas");
    surface.width = mapState.pixelWidth;
    surface.height = mapState.pixelHeight;
    const surfaceCtx = surface.getContext("2d");
    surfaceCtx.imageSmoothingEnabled = false;
    surfaceCtx.fillStyle = "#17150f";
    surfaceCtx.fillRect(0, 0, surface.width, surface.height);

    mapState.layers.forEach((layer) => {
      for (let y = 0; y < mapState.height; y += 1) {
        for (let x = 0; x < mapState.width; x += 1) {
          const gid = layer.gids[y * mapState.width + x];
          if (!gid) continue;
          drawTile(surfaceCtx, gid, x * mapState.tileWidth, y * mapState.tileHeight);
        }
      }
    });

    mapState.surface = surface;
  }

  function drawTile(targetCtx, gid, dx, dy) {
    const tileset = findTileset(gid);
    if (!tileset) return;
    const localId = gid - tileset.firstgid;
    if (localId < 0 || localId >= tileset.tilecount) return;

    const sx = (localId % tileset.columns) * tileset.tileWidth;
    const sy = Math.floor(localId / tileset.columns) * tileset.tileHeight;
    const drawY = dy - (tileset.tileHeight - mapState.tileHeight);
    targetCtx.drawImage(
      tileset.image,
      sx,
      sy,
      tileset.tileWidth,
      tileset.tileHeight,
      dx,
      drawY,
      tileset.tileWidth,
      tileset.tileHeight,
    );
  }

  function findTileset(gid) {
    for (let index = mapState.tilesets.length - 1; index >= 0; index -= 1) {
      if (gid >= mapState.tilesets[index].firstgid) return mapState.tilesets[index];
    }
    return null;
  }

  function getCoverZoom() {
    const rect = els.canvas.getBoundingClientRect();
    if (!rect.width || !rect.height || !mapState.pixelWidth || !mapState.pixelHeight) return 1;
    const scaleX = rect.width / mapState.pixelWidth;
    const scaleY = rect.height / mapState.pixelHeight;
    return Math.max(scaleX, scaleY);
  }

  function fitMapToStage({ preserveZoom = false } = {}) {
    const coverZoom = getCoverZoom();
    camera.minZoom = coverZoom;
    camera.maxZoom = Math.max(coverZoom * 5, 1.5);
    camera.zoom = preserveZoom
      ? Math.min(camera.maxZoom, Math.max(camera.zoom, camera.minZoom))
      : camera.minZoom;
    if (!preserveZoom) {
      camera.x = mapState.pixelWidth / 2;
      camera.y = mapState.pixelHeight / 2;
    }
    clampCamera();
  }

  function resizeCanvas() {
    const rect = els.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    els.canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    els.canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (mapReady) fitMapToStage({ preserveZoom: true });
    draw();
  }

  function draw() {
    const rect = els.canvas.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    ctx.save();
    ctx.fillStyle = "#090b0d";
    ctx.fillRect(0, 0, width, height);

    if (!mapReady || !mapState.surface) {
      ctx.restore();
      return;
    }

    ctx.imageSmoothingEnabled = false;
    const viewX = camera.x - width / (2 * camera.zoom);
    const viewY = camera.y - height / (2 * camera.zoom);
    const drawX = Math.floor(-viewX * camera.zoom) - 1;
    const drawY = Math.floor(-viewY * camera.zoom) - 1;
    const drawWidth = Math.ceil(mapState.pixelWidth * camera.zoom) + 2;
    const drawHeight = Math.ceil(mapState.pixelHeight * camera.zoom) + 2;
    ctx.drawImage(
      mapState.surface,
      drawX,
      drawY,
      drawWidth,
      drawHeight,
    );

    drawLocations(viewX, viewY);
    drawAgents(viewX, viewY);
    ctx.restore();
  }

  function drawLocations(viewX, viewY) {
    ctx.save();
    simState.locations.forEach((location) => {
      const selected = selectedLocationId === location.id;
      const x = (location.x - viewX) * camera.zoom;
      const y = (location.y - viewY) * camera.zoom;
      const w = Math.max(location.width * camera.zoom, 18);
      const h = Math.max(location.height * camera.zoom, 18);

      if (selected) {
        ctx.strokeStyle = "rgba(117, 213, 226, 0.95)";
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, w, h);
      } else if (camera.zoom > 0.55 && location.type === "backstage") {
        ctx.strokeStyle = "rgba(117, 213, 226, 0.28)";
        ctx.lineWidth = 1;
        ctx.strokeRect(x, y, w, h);
      }

      if (selected || camera.zoom > 0.78) {
        ctx.font = "600 11px 'Segoe UI', Arial, sans-serif";
        ctx.fillStyle = selected ? "#eafcff" : "rgba(244, 219, 178, 0.75)";
        ctx.fillText(getLocationLabel(location.id), x + 4, y + 13);
      }
    });
    ctx.restore();
  }

  function drawAgents(viewX, viewY) {
    Object.entries(simState.agents).forEach(([agentId, agent]) => {
      const point = getAgentWorldPoint(agentId, agent);
      if (!point) return;

      const x = (point.x - viewX) * camera.zoom;
      const y = (point.y - viewY) * camera.zoom;
      const awakening = Number(agent.awakening || 0);
      const isGuest = getAgentType(agentId) === "guest";
      const isSelected = selectedAgentId === agentId;
      const radius = Math.max(5, Math.min(10, 6 * Math.sqrt(camera.zoom)));

      ctx.save();
      ctx.beginPath();
      ctx.arc(x, y, radius + (awakening > 20 ? 5 : 2), 0, Math.PI * 2);
      ctx.strokeStyle = awakening > 20 ? "rgba(117, 213, 226, 0.72)" : "rgba(238, 179, 91, 0.35)";
      ctx.lineWidth = isSelected ? 3 : 1.5;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fillStyle = isGuest ? "#e8d9a8" : awakening > 20 ? "#75d5e2" : "#c78642";
      ctx.fill();
      ctx.strokeStyle = "#111417";
      ctx.lineWidth = 2;
      ctx.stroke();

      if (isSelected || camera.zoom > 0.9) {
        ctx.font = "700 11px 'Segoe UI', Arial, sans-serif";
        ctx.textAlign = "center";
        ctx.fillStyle = "#fff3d2";
        ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
        ctx.shadowBlur = 5;
        ctx.fillText(getAgentLabel(agentId), x, y - 13);
      }
      ctx.restore();
    });
  }

  function getAgentWorldPoint(agentId, agent) {
    const locationId = agent.location || agent.current_location || agent.location_id;
    let location = simState.locationById.get(locationId);
    if (!location && typeof locationId === "string") {
      location = simState.locations.find((item) => item.id.includes(locationId) || locationId.includes(item.id));
    }
    if (!location) return null;

    const centerX = location.x + Math.max(location.width, 28) / 2;
    const centerY = location.y + Math.max(location.height, 28) / 2;
    const colocated = Object.entries(simState.agents)
      .filter(([, item]) => (item.location || item.current_location || item.location_id) === locationId)
      .map(([id]) => id)
      .sort();
    const index = Math.max(0, colocated.indexOf(agentId));
    const angle = (stableHash(agentId) % 360) * Math.PI / 180;
    const ring = 10 + index * 6;
    return {
      x: centerX + Math.cos(angle) * ring,
      y: centerY + Math.sin(angle) * ring,
    };
  }

  function updateAgentList() {
    const entries = Object.entries(simState.agents)
      .sort((a, b) => Number(b[1].awakening || 0) - Number(a[1].awakening || 0));
    els.agentCount.textContent = String(entries.length);
    els.awakeCount.textContent = String(entries.filter(([, agent]) => Number(agent.awakening || 0) >= 20).length);
    els.guestCount.textContent = String(entries.filter(([id]) => getAgentType(id) === "guest").length);

    if (!entries.length) {
      els.agentList.innerHTML = `<p class="empty-copy">Waiting for a backend snapshot.</p>`;
      return;
    }

    els.agentList.innerHTML = "";
    entries.forEach(([agentId, agent]) => {
      const button = document.createElement("button");
      button.className = `agent-row${selectedAgentId === agentId ? " is-selected" : ""}`;
      button.type = "button";
      button.innerHTML = `
        <span class="agent-row__sigil">${getAgentType(agentId) === "guest" ? "G" : "H"}</span>
        <span class="agent-row__body">
          <strong>${escapeHtml(getAgentLabel(agentId))}</strong>
          <small>${escapeHtml(getLocationLabel(agent.location))}</small>
        </span>
        <span class="agent-row__score">${Number(agent.awakening || 0)}</span>
      `;
      button.addEventListener("click", () => selectAgent(agentId));
      els.agentList.appendChild(button);
    });
  }

  function selectAgent(agentId) {
    selectedAgentId = agentId;
    selectedLocationId = simState.agents[agentId] ? simState.agents[agentId].location : null;
    closeLocationDialog({ redraw: false });
    updateAgentList();
    updateInspector();
    centerOnSelection();
    draw();
  }

  function openLocationDialog(locationId, event) {
    selectedLocationId = locationId;
    renderLocationDialog(locationId);
    positionLocationDialog(event);
    els.locationDialog.hidden = false;
    draw();
  }

  function closeLocationDialog({ redraw = true } = {}) {
    els.locationDialog.hidden = true;
    selectedLocationId = selectedAgentId && simState.agents[selectedAgentId]
      ? simState.agents[selectedAgentId].location
      : null;
    if (redraw) draw();
  }

  function positionLocationDialog(event) {
    const rect = els.mapStage.getBoundingClientRect();
    const width = Math.min(420, Math.max(260, rect.width - 32));
    const rawX = event.clientX - rect.left;
    const rawY = event.clientY - rect.top;
    const x = Math.min(Math.max(rawX, width / 2 + 16), rect.width - width / 2 - 16);
    const y = Math.min(Math.max(rawY, 96), rect.height - 18);
    els.locationDialog.style.setProperty("--dialog-width", `${width}px`);
    els.locationDialog.style.left = `${x}px`;
    els.locationDialog.style.top = `${y}px`;
    els.locationDialog.dataset.placement = rawY < 240 ? "below" : "above";
  }

  function renderLocationDialog(locationId) {
    const location = simState.locationById.get(locationId);
    if (!location) return;

    const scene = simState.scenes[locationId] || {};
    const present = scene.chunks && scene.chunks.present_agents
      ? scene.chunks.present_agents
      : "No local presence reported.";

    els.locationDialogType.textContent = location.type ? titleCase(location.type) : "Location";
    els.locationDialogTitle.textContent = getLocationLabel(locationId);
    els.locationDialogMeta.textContent = `${titleCase(location.region || "park")} / ${countAgentsAt(locationId)} active signals`;
    els.locationDialogPresence.textContent = Array.isArray(present) ? present.join(", ") : String(present);
    renderLocationDialogEvents(getSceneEvents(locationId));
  }

  function renderLocationDialogEvents(events) {
    if (!events.length) {
      els.locationDialogEvents.innerHTML = `<p>No recent events.</p>`;
      return;
    }

    els.locationDialogEvents.innerHTML = events
      .map((event) => `<p>${escapeHtml(String(event))}</p>`)
      .join("");
  }

  function updateInspector() {
    if (selectedAgentId && simState.agents[selectedAgentId]) {
      renderAgentInspector(selectedAgentId, simState.agents[selectedAgentId]);
      return;
    }

    els.sceneType.textContent = "Person";
    els.selectionTitle.textContent = "No character selected";
    els.selectionMeta.textContent = mapReady
      ? "Click a host or guest marker, or choose a name from the roster."
      : "Map telemetry is loading.";
    els.awakeningMeter.style.width = "0%";
    els.conditionText.textContent = snapshotReady ? "No character selected." : "Awaiting telemetry.";
    renderEvents([]);
  }

  function renderAgentInspector(agentId, agent) {
    const location = simState.locationById.get(agent.location);
    const awakening = Math.max(0, Math.min(100, Number(agent.awakening || 0)));
    els.sceneType.textContent = getAgentType(agentId) === "guest" ? "Guest" : "Host";
    els.selectionTitle.textContent = getAgentLabel(agentId);
    els.selectionMeta.textContent = `${getLocationLabel(agent.location)} / ${agent.emotion || "Neutral"}`;
    els.awakeningMeter.style.width = `${awakening}%`;
    els.conditionText.textContent = `Awakening ${awakening}/100. Health ${agent.health ?? "-"} / Energy ${agent.energy ?? "-"}.`;
    renderEvents(getSceneEvents(location && location.id));
  }

  function getSceneEvents(locationId) {
    if (!locationId) return [];
    const scene = simState.scenes[locationId] || {};
    const events = scene.chunks && scene.chunks.recent_events;
    return Array.isArray(events) ? events.slice(-5).reverse() : [];
  }

  function renderEvents(events) {
    if (!events.length) {
      els.eventList.innerHTML = `<p class="empty-copy">No events loaded.</p>`;
      return;
    }

    els.eventList.innerHTML = events
      .map((event) => `<p>${escapeHtml(String(event))}</p>`)
      .join("");
  }

  function countAgentsAt(locationId) {
    return Object.values(simState.agents)
      .filter((agent) => agent.location === locationId)
      .length;
  }

  function centerOnSelection() {
    const target = selectedAgentId && simState.agents[selectedAgentId]
      ? getAgentWorldPoint(selectedAgentId, simState.agents[selectedAgentId])
      : selectedLocationId && simState.locationById.get(selectedLocationId);
    if (!target) return;
    camera.x = target.x + Math.max(target.width || 0, 0) / 2;
    camera.y = target.y + Math.max(target.height || 0, 0) / 2;
    clampCamera();
  }

  function screenToWorld(clientX, clientY) {
    const rect = els.canvas.getBoundingClientRect();
    return {
      x: camera.x + (clientX - rect.left - rect.width / 2) / camera.zoom,
      y: camera.y + (clientY - rect.top - rect.height / 2) / camera.zoom,
    };
  }

  function clampCamera() {
    if (!mapState.pixelWidth) return;
    const rect = els.canvas.getBoundingClientRect();
    const halfW = rect.width / (2 * camera.zoom);
    const halfH = rect.height / (2 * camera.zoom);

    if (halfW * 2 >= mapState.pixelWidth) {
      camera.x = mapState.pixelWidth / 2;
    } else {
      camera.x = Math.min(Math.max(camera.x, halfW), mapState.pixelWidth - halfW);
    }

    if (halfH * 2 >= mapState.pixelHeight) {
      camera.y = mapState.pixelHeight / 2;
    } else {
      camera.y = Math.min(Math.max(camera.y, halfH), mapState.pixelHeight - halfH);
    }
  }

  function handleCanvasClick(event) {
    if (!mapReady) return;
    const world = screenToWorld(event.clientX, event.clientY);
    const agentHit = findAgentAt(world);
    if (agentHit) {
      selectAgent(agentHit);
      return;
    }

    const locationHit = findLocationAt(world);
    if (locationHit) {
      openLocationDialog(locationHit.id, event);
      return;
    }

    closeLocationDialog();
  }

  function findAgentAt(world) {
    let best = null;
    let bestDistance = Infinity;
    Object.entries(simState.agents).forEach(([agentId, agent]) => {
      const point = getAgentWorldPoint(agentId, agent);
      if (!point) return;
      const distance = Math.hypot(point.x - world.x, point.y - world.y);
      if (distance < bestDistance && distance < 18 / camera.zoom) {
        best = agentId;
        bestDistance = distance;
      }
    });
    return best;
  }

  function findLocationAt(world) {
    const candidates = simState.locations
      .filter((location) => {
        const width = Math.max(location.width, 24);
        const height = Math.max(location.height, 24);
        return world.x >= location.x
          && world.x <= location.x + width
          && world.y >= location.y
          && world.y <= location.y + height;
      })
      .sort((a, b) => (a.width * a.height) - (b.width * b.height));
    return candidates[0] || null;
  }

  function getLocationLabel(locationId) {
    if (!locationId) return "Unknown";
    return LOCATION_LABELS[locationId] || titleCase(String(locationId).replace(/_/g, " "));
  }

  function getAgentLabel(agentId) {
    return AGENT_LABELS[agentId] || titleCase(String(agentId).replace(/_/g, " "));
  }

  function getAgentType(agentId) {
    return agentId === "william" || agentId === "logan" ? "guest" : "host";
  }

  function stableHash(input) {
    return String(input).split("").reduce((hash, char) => {
      return ((hash << 5) - hash + char.charCodeAt(0)) | 0;
    }, 0) >>> 0;
  }

  function titleCase(value) {
    return String(value)
      .split(/\s+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  els.enterButton.addEventListener("click", startStory);
  els.storyIntro.addEventListener("click", advanceFromInput);
  els.tickButton.addEventListener("click", sendStartTick);
  els.rightPanelToggle.addEventListener("click", () => {
    setRightPanelOpen(els.rightPanel.hidden);
  });
  els.rightPanelClose.addEventListener("click", () => setRightPanelOpen(false));
  els.locationDialogClose.addEventListener("click", () => closeLocationDialog());

  document.addEventListener("keydown", (event) => {
    if (!els.storyIntro.hidden) {
      advanceFromInput(event);
      return;
    }

    if (event.key === "Escape" && !els.locationDialog.hidden) {
      closeLocationDialog();
      return;
    }

    if (event.key === "Enter" && !appStarted) {
      startStory(event);
    }
  });

  els.canvas.addEventListener("pointerdown", (event) => {
    dragState = {
      x: event.clientX,
      y: event.clientY,
      moved: false,
    };
    els.canvas.setPointerCapture(event.pointerId);
  });

  els.canvas.addEventListener("pointermove", (event) => {
    if (!dragState || !mapReady) return;
    const dx = event.clientX - dragState.x;
    const dy = event.clientY - dragState.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) dragState.moved = true;
    camera.x -= dx / camera.zoom;
    camera.y -= dy / camera.zoom;
    dragState.x = event.clientX;
    dragState.y = event.clientY;
    clampCamera();
    draw();
  });

  els.canvas.addEventListener("pointerup", (event) => {
    if (dragState && !dragState.moved) handleCanvasClick(event);
    dragState = null;
  });

  els.canvas.addEventListener("wheel", (event) => {
    if (!mapReady) return;
    event.preventDefault();
    const before = screenToWorld(event.clientX, event.clientY);
    const factor = event.deltaY > 0 ? 0.9 : 1.1;
    camera.minZoom = getCoverZoom();
    camera.zoom = Math.min(camera.maxZoom, Math.max(camera.minZoom, camera.zoom * factor));
    const after = screenToWorld(event.clientX, event.clientY);
    camera.x += before.x - after.x;
    camera.y += before.y - after.y;
    clampCamera();
    draw();
  }, { passive: false });

  window.addEventListener("resize", resizeCanvas);
  updateTickButton();
})();
