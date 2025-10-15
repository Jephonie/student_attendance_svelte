<script>
  import { onMount } from "svelte";

  // UI state
  let showForm = false;
  let showFacePage = false;
  let showLoginPage = false;
  let isRecognized = false;
  let isDetecting = false;

  // Settings 🔧
  let showSettingsAuth = false;
  let showSettingsPage = false;
  // for authentication
  let settingsUser = "";
  let settingsPass = "";
  let settingsError = "";
  // 🌐 Settings values
  let deviceName = localStorage.getItem("deviceName") || "";
  // Auto-save device name when changed
  $: localStorage.setItem("deviceName", deviceName);

  // QR scanner
  let scannerActive = false;
  let html5QrCode;

  // form fields
  let firstName = "";
  let middleInitial = "";
  let surname = "";
  let studentId = "";

  // saved temporarily (only sent after Save)
  let registrationData = {};

  // camera / capture
  let video;
  let canvas;
  let ctx;
  let stream;
  let cameras = [];
  let selectedCamera = "";
  let faceCamera = "";
  let faceStep = 1; // 1,2,3
  let capturedImages = { pic1: "", pic2: "", pic3: "" };
  let faceStatus = "none"; // front | left | right | none
  let faceDetectionBox = null; // store latest face position
  let overlayCanvas;
  let overlayCtx;

  let loginVideo;
  let loginCanvas;
  let loginCtx;
  let loginStream;
  let loginCamera = null;
  let loginMessage = "";
  let loginMessageColor = "black"; 
  let detectionInterval;
  let loginImageUrl = "";
  let loginImageUrls = [];

  const CAMERA_LED_URL = "http://10.249.38.255:5001"; // or http://<raspi-ip>:5001 if remote
  let SERVER_URL = "http://10.249.38.91:3000";

  // On mount: auto-select EMEET USB webcam
  onMount(async () => {
    const devices = await navigator.mediaDevices.enumerateDevices();
    cameras = devices.filter(d => d.kind === "videoinput");

    // Find EMEET camera
    const emeetCam = cameras.find(cam =>
      (cam.label || "").toLowerCase().includes("emeet")
    );

    if (emeetCam) {
      selectedCamera = emeetCam.deviceId;
      faceCamera = emeetCam.deviceId;
      console.log("✅ EMEET camera selected:", emeetCam.label);
    } else {
      // fallback if EMEET not found
      selectedCamera = cameras[0]?.deviceId || "";
      faceCamera = selectedCamera;
      console.warn("⚠ EMEET camera not found, using default:", cameras[0]?.label);
    }
  });


  // -------------------------
  // QR scanner (html5-qrcode) - dynamic import so SSR doesn't break
  // -------------------------
  async function startScanner() {
    if (scannerActive) return;
    scannerActive = true;

    try {
      const { Html5Qrcode } = await import("html5-qrcode"); // dynamic import
      html5QrCode = new Html5Qrcode("qr-reader");

      // Always use the EMEET camera (already set in onMount)
      const cameraConfig = { deviceId: { exact: selectedCamera } };

      await startCameraLED();

      await html5QrCode.start(
        cameraConfig,
        { fps: 10, qrbox: 250 },
        (decodedText, decodedResult) => {
          console.log("QR scanned:", decodedText);
          try {
            fillFormFromQR(decodedText);
          } catch (err) {
            console.warn("QR parse problem:", err);
            alert("Scanned: " + decodedText);
          }
          stopScanner();
        },
        (errorMessage) => {
          // scan errors (you can keep this quiet or log)
        }
      );


      console.log("QR scanner started");
      scannerActive = true;
    } catch (err) {
      console.error("Could not start QR scanner:", err);
      alert("Could not start QR scanner: " + (err.message || err));
      scannerActive = false;
    }
  }

  async function stopScanner() {
    if (html5QrCode) {
      try {
        await html5QrCode.stop();
        html5QrCode.clear();
      } catch (err) {
        console.warn("Error stopping QR scanner:", err);
      }
    }
    scannerActive = false;
    stopCameraLED();
  }

  function fillFormFromQR(data) {
    // Example of the ID QR you showed:
    // "GERJEN MAE L. ESPINOSA 2022304979 BSET TN"
    // We'll be flexible: assume last tokens are numeric id, course, section,
    // take first 3 or 4 tokens for name pieces.
    const parts = data.trim().split(/\s+/);
    if (parts.length < 4) throw new Error("Invalid QR format");

    // find student number (student ID)
    const numericIndex = parts.findIndex(p => /^\d{4,}$/.test(p));
    if (numericIndex === -1) throw new Error("Student ID not found");

    const nameParts = parts.slice(0, numericIndex);
    const studentIdToken = parts[numericIndex]; // ← Student ID

    // Assign names
    if (nameParts.length >= 3) {
      firstName = nameParts.slice(0, -2).join(" ");
      middleInitial = nameParts[nameParts.length - 2].replace(".", "");
      surname = nameParts[nameParts.length - 1];
    } else if (nameParts.length === 2) {
      firstName = nameParts[0];
      middleInitial = "";
      surname = nameParts[1];
    } else {
      firstName = nameParts[0];
      middleInitial = "";
      surname = "";
    }

    // Student ID
    studentId = studentIdToken;

    console.log("Filled from QR:", { firstName, middleInitial, surname, studentId });
  }

  async function submitForm() {
    // Save form data locally, but don't call backend yet
    registrationData = {
      firstName,
      middleInitial,
      surname,
      studentId
    };

    // Move to face capture page
    showForm = false;
    showFacePage = true;

    // Reset canvas/context
    ctx = null;
    if (canvas) {
      canvas.width = 0;
      canvas.height = 0;
    }

    // Start camera and automatic capture
    setTimeout(() => startScan(), 300);
  }


  function resetForm() {
    firstName = "";
    middleInitial = "";
    surname = "";
    studentId = "";
    registrationData = {};
    capturedImages = { pic1: "", pic2: "", pic3: "" };
    faceStep = 1;
    showForm = false;
    showFacePage = false;
  }

  // Take snapshot from video
  function takeSnapshot() {
    const tempCanvas = document.createElement("canvas");
    const ctx = tempCanvas.getContext("2d");

    if (!video || !video.videoWidth) {
      console.warn("⚠ Video not ready for snapshot");
      return null;
    }

    // target size for FaceAPI detection
    const TARGET_WIDTH = 640;
    const TARGET_HEIGHT = 480;

    tempCanvas.width = TARGET_WIDTH;
    tempCanvas.height = TARGET_HEIGHT;

    // draw scaled image from video
    ctx.drawImage(video, 0, 0, TARGET_WIDTH, TARGET_HEIGHT);

    return tempCanvas.toDataURL("image/jpeg");
  }
  async function checkOrientation() {
    const frame = takeSnapshot();
    const res = await fetch(`${SERVER_URL}/check-face`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: frame })
    });
    return res.json(); // { orientation: "front" | "left" | "right" | "none" }
  }
  
  // -------------------------
  // Face camera functions
  // -------------------------
  async function startScan() {
    try {
      console.log("🎥 Starting smooth scan camera...");

      // Dynamically pick the selected camera (like loginCamera)
      const devices = await navigator.mediaDevices.enumerateDevices();
      overlayCtx = overlayCanvas?.getContext("2d");
      const selected = devices.find(
        d => d.kind === "videoinput" && (d.deviceId === selectedCamera || d.deviceId === faceCamera)
      );
      await startCameraLED();
      let constraints;
      if (selected) {
        constraints = { video: { deviceId: { exact: selected.deviceId } } };
      } else {
        console.warn("⚠ Selected camera not found, using default camera.");
        constraints = { video: true };
      }

      // lighter constraints = smoother video
      stream = await navigator.mediaDevices.getUserMedia(constraints);
      video.srcObject = stream;

      await video.play().catch(err => {
        console.warn("⚠ Video autoplay blocked, waiting for user gesture:", err);
      });

      console.log("✅ Camera started:", video.videoWidth, "x", video.videoHeight);

      if (!ctx && canvas) ctx = canvas.getContext("2d");

      // start your scanning logic
      autoCaptureSequence();

    } catch (err) {
      console.error("❌ Camera start error:", err);
      alert("Unable to access camera: " + (err.message || err));
    }
  }

  async function autoCaptureSequence() {
    const instructions = {
      1: "Look straight ahead",
      2: "Turn your face slightly to the RIGHT",
      3: "Turn your face slightly to the LEFT"
    };

    while (faceStep <= 3) {
      let captured = false;
      console.log("🟢 Waiting for:", instructions[faceStep]);

      while (!captured) {
        const { orientation } = await checkOrientation();
        faceStatus = orientation;

        if (faceStep === 1 && orientation === "front") captured = true;
        if (faceStep === 2 && orientation === "right") captured = true;
        if (faceStep === 3 && orientation === "left") captured = true;

        if (captured) {
          const frame = takeSnapshot();
          capturedImages[`pic${faceStep}`] = frame;
          console.log(`✅ Auto captured step ${faceStep}`);
          faceStep++;
          await new Promise(res => setTimeout(res, 1000));
        }

        await new Promise(res => setTimeout(res, 300));
      }
    }

    // Check if face already exists on server before sending registration
    const duplicateCheckRes = await fetch(`${SERVER_URL}/login-recognize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: capturedImages.pic1 })
    });

    const duplicateData = await duplicateCheckRes.json();
    if (duplicateData.message.includes("Welcome back")) {
      alert(`❌ This face is already registered: ${duplicateData.message}`);
      stopCamera();
      resetForm();
      return;
    }

    // If not duplicate → send to registration
    await saveData();
  }

  async function saveData() {
    if (!capturedImages.pic1 || !capturedImages.pic2 || !capturedImages.pic3) {
      alert("Please capture all 3 pictures.");
      return;
    }

    const payload = {...registrationData,images: capturedImages };

    console.log("Sending payload to server:", {
      ...registrationData,
      pic1Len: capturedImages.pic1.length,
      pic2Len: capturedImages.pic2.length,
      pic3Len: capturedImages.pic3.length
    });

    try {
      const res = await fetch(`${SERVER_URL}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      console.log("Server response status:", res.status);

      const raw = await res.text(); // read full text (debugging)
      console.log("Server raw response:", raw);

      let result;
      try {
        result = JSON.parse(raw);
      } catch {
        result = {};
      }
      alert(result.message || "Saved successfully!");

      stopCamera();
      resetForm();
    } catch (err) {
      console.error("SaveData error:", err);
      alert("Failed to save: " + (err.message || err));
    }
  }
  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      stream = null;
    }
    if (video) {
      video.srcObject = null;
    }
    stopCameraLED();
  }
  
  async function startLoginCamera() {
    try {
      // Dynamically find EMEET camera id
      const devices = await navigator.mediaDevices.enumerateDevices();
      const emeetCam = devices.find(
        d => d.kind === "videoinput" && (d.label || "").toLowerCase().includes("emeet")
      );

      await startCameraLED();

      let constraints;
      if (emeetCam) {
        constraints = { video: { deviceId: { exact: emeetCam.deviceId } } };
      } else {
        console.warn("⚠ EMEET camera not found, falling back to default.");
        constraints = { video: true };
      }

      loginStream = await navigator.mediaDevices.getUserMedia(constraints);
      loginVideo.srcObject = loginStream;

      // Play may fail due to autoplay policy — catch but don’t treat as camera error
      loginVideo.play().catch(err => {
        console.warn("⚠ Video autoplay blocked, user interaction needed:", err);
      });

      loginCtx = loginCanvas.getContext("2d");

      if (detectionInterval) clearInterval(detectionInterval);
      detectionInterval = setInterval(sendFrameForDetection, 500);

    } catch (err) {
      console.error("Login camera error:", err);
      alert("❌ Could not start login camera at all");
      showLoginPage = false;
    }
  }

  async function sendFrameForDetection() {
    // Prevent overlapping detections
    if (
      isRecognized ||
      isDetecting ||
      !loginCtx ||
      !loginVideo ||
      !loginVideo.srcObject ||
      loginVideo.readyState < 2
    ) return; 
    isDetecting = true; // Mark as detecting

    // Draw the current video frame to the canvas
    loginCanvas.width = loginVideo.videoWidth;
    loginCanvas.height = loginVideo.videoHeight;
    loginCtx.drawImage(loginVideo, 0, 0, loginCanvas.width, loginCanvas.height);

    const imageData = loginCanvas.toDataURL("image/png");

    try {
      const res = await fetch(`${SERVER_URL}/login-recognize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: imageData }),
      });

      const data = await res.json();

      if (data.message.includes("Welcome") || data.message.includes("Stranger")) {
        isRecognized = true;       // Lock detection while showing result
        loginMessage = data.message; // Show message

        if (data.message.includes("Welcome")) {
          const studentId = data.studentId; // get ID from server
          loginImageUrl = `${SERVER_URL}/face/${studentId}_pic1.png`;
          console.log("Thumbnail URL:", loginImageUrl);
        } else {
          loginImageUrl = null; // Stranger → no image
        }
        if (detectionInterval) clearInterval(detectionInterval);

        // Reset recognition after 5 seconds so next login can be detected
        setTimeout(() => {
          isRecognized = false;
          loginMessage = "";
          loginImageUrl = "";
          showLoginPage = false;
          stopLoginCamera();
          // Restart detection interval
          detectionInterval = setInterval(sendFrameForDetection, 500);
        }, 3000);
      }
    } catch (err) {
      console.error("Recognition error:", err);
    } finally {
      isDetecting = false; // Ready for next frame
    }
  }

  function stopLoginCamera() {
    if (detectionInterval) {
      clearInterval(detectionInterval);
      detectionInterval = null;
    }
    if (loginStream) {
      loginStream.getTracks().forEach((t) => t.stop());
      loginStream = null;
    }
    if (loginVideo) loginVideo.srcObject = null;

    stopCameraLED();
  }

  function saveDeviceName() {
    localStorage.setItem("deviceName", deviceName);
    alert("✅ Device name saved!");
  }
  function openSettingsAuth() {
    showSettingsAuth = true;
  }
  function checkSettingsLogin() {
    const validUser = "admin";
    const validPass = "1234";

    if (settingsUser === validUser && settingsPass === validPass) {
      showSettingsAuth = false;
      showSettingsPage = true;
      settingsError = "";
    } else {
      settingsError = "Invalid username or password";
    }
  }
  function closeSettings() {
    showSettingsPage = false;
  }

  async function startCameraLED() {
    try {
      await fetch(`${CAMERA_LED_URL}/start_camera`, { method: "POST" });
      console.log("LED ON + Camera started");
    } catch (err) {
      console.error("Error starting camera LED:", err);
    }
  }

  async function stopCameraLED() {
    try {
      await fetch(`${CAMERA_LED_URL}/stop_camera`, { method: "POST" });
      console.log("LED OFF + Camera stopped");
    } catch (err) {
      console.error("Error stopping camera LED:", err);
    }
  }

</script>

<div class="screen">
  {#if !showForm && !showFacePage && !showLoginPage && !showSettingsAuth && !showSettingsPage}
    <div class="main-buttons">
      <button class="big-btn login-btn" on:click={() => { showLoginPage = true; startLoginCamera(); }}>
        Login
      </button>
    </div>

    <div class="bottom-button">
      <button class="big-btn register-btn" on:click={() => showForm = true}>
        Register
      </button>
    </div>

    <button class="settings-btn" on:click={openSettingsAuth}>
      <span class="gear">⚙️</span>
    </button>
  {/if}
  {#if showSettingsAuth}
    <div class="settings-auth">
      <h2>Settings Login</h2>
      <input type="text" placeholder="Username" bind:value={settingsUser} />
      <input type="password" placeholder="Password" bind:value={settingsPass} />

      {#if settingsError}
        <p style="color:red;">{settingsError}</p>
      {/if}

      <div class="actions">
        <button on:click={checkSettingsLogin}>Enter</button>
        <button on:click={() => showSettingsAuth = false}>Cancel</button>
      </div>
    </div>
  {/if}


  {#if showSettingsPage}
    <div class="settings-page">
      <h2>⚙ Settings</h2>
      <p>Here you can configure admin or system settings.</p>

      <!-- 🖥 Device Name -->
      <label>
        Device Name:
        <input type="text" bind:value={deviceName} placeholder="Enter device name" />
      </label>

      <!-- 🌐 Server URL -->
      <label>
        Server URL:
        <input type="text" bind:value={SERVER_URL} />
      </label>

      <button on:click={closeSettings}>Back</button>
    </div>
  {/if}

  {#if showForm}
    <!-- Registration form -->
    <form class="form" on:submit|preventDefault={submitForm}>
      <label>
        First Name:
        <input type="text" bind:value={firstName} required />
      </label>

      <label>
        Middle Initial:
        <input type="text" maxlength="2" bind:value={middleInitial} />
      </label>

      <label>
        Surname:
        <input type="text" bind:value={surname} required />
      </label>

      <label>
        Student ID:
        <input type="text" bind:value={studentId} required />
      </label>

      <div class="actions">
        <button type="submit" class="submit-btn">Submit</button>
        <button type="button" class="cancel-btn" on:click={resetForm}>
          Cancel
        </button>
      </div>

      <div class="scanner-actions">
        {#if !scannerActive}
          <button type="button" class="scan-btn" on:click={startScanner}>
            📷 Scan QR
          </button>
        {:else}
          <button type="button" class="stop-btn" on:click={stopScanner}>
            ✖ Stop Scanner
          </button>
        {/if}
      </div>

      <div id="qr-reader" class="qr-reader"></div>
    </form>
  {/if}

  {#if showFacePage}
    <div class="face-page">
      <h2>Face Capture Step {faceStep} for {registrationData.firstName} {registrationData.surname}</h2>

      <div class="video-container">
        <video bind:this={video} autoplay muted playsinline class="live-video"></video>
      </div>

      <div class="preview">
        {#if capturedImages.pic1}
          <img src={capturedImages.pic1} width="150" alt="Step 1" />
        {/if}
        {#if capturedImages.pic2}
          <img src={capturedImages.pic2} width="150" alt="Step 2" />
        {/if}
        {#if capturedImages.pic3}
          <img src={capturedImages.pic3} width="150" alt="Step 3" />
        {/if}
      </div>

      <!-- Final status only -->
      {#if faceStep === 4}
        <p style="font-weight: bold; color: green; font-size: 1.2rem;">
          ✅ Face capture complete — data saved automatically
        </p>
      {/if}
    </div>
  {/if}

  {#if showLoginPage}
    <div class="login-page">
      <h2>Login with Face Recognition</h2>
      <!-- svelte-ignore a11y_media_has_caption -->
      <video bind:this={loginVideo} autoplay playsinline muted class="camera-video"></video>
      <canvas bind:this={loginCanvas} style="display:none"></canvas>

      <!-- 👇 Result message + thumbnail -->
      {#if loginMessage}
        <div style="margin-top: 1rem; font-weight: bold; color: {loginMessageColor}; display:flex; align-items:center; gap:10px;">
          {#if loginImageUrl}
            <img src={loginImageUrl} alt="Recognized face" style="width:60px; height:60px; border-radius:8px; object-fit:cover; border:2px solid {loginMessageColor};" />
          {/if}
          <span>{loginMessage}</span>
        </div>
      {/if}
    </div>
  {/if}

  {#if loginMessage}
    <div class="login-result">
      {#if loginImageUrl}
        <img
          src={loginImageUrl}
          alt="Recognized face"
          style="border-color: {loginMessageColor};"
        />
      {/if}
      <span class="login-message" style="color: {loginMessageColor};">
        {loginMessage}
      </span>
    </div>
  {/if}

  {#if loginImageUrls && loginImageUrls.length > 0}
    <div class="login-result-below">
      {#each loginImageUrls as url}
        <img src={SERVER_URL + url} alt="Recognized face" />
      {/each}
    </div>
  {/if}

</div>

<style>
  .screen {
    width: 600px;
    height: 1024px;
    display: flex;
    flex-direction: column; 
    align-items: center;
    justify-content: space-between;
    background: #f9f9f9;
    padding: 40px 0;
    touch-action: manipulation;
  }

  .big-btn {
    font-size: 2rem;
    margin: 10px 0; 
    padding: 20px 40px;
    border: none;
    border-radius: 12px;
    background: #0077cc;
    color: white;
    cursor: pointer;
    touch-action: manipulation;
  }

  .login-btn {
    position: relative;
    top: 120px; /* move down slightly */
  }

  .register-btn {
    position: relative;
    bottom: 700px; /* move up slightly if needed */
  }

  .form {
    display: flex;
    flex-direction: column;
    gap: 20px;
    width: 80%;
    max-width: 500px;
  }

  label {
    font-size: 1.2rem;
    display: flex;
    flex-direction: column;
  }

  input {
    padding: 12px;
    font-size: 1.2rem;
    border: 1px solid #ccc;
    border-radius: 8px;
    touch-action: manipulation;
  }

  .actions {
    display: flex;
    justify-content: space-between;
    gap: 10px;
  }

  .submit-btn {
    flex: 1;
    background: #28a745;
    color: white;
    border: none;
    padding: 15px;
    border-radius: 8px;
    font-size: 1.2rem;
    cursor: pointer;
    touch-action: manipulation;
  }

  .cancel-btn {
    flex: 1;
    background: #dc3545;
    color: white;
    border: none;
    padding: 15px;
    border-radius: 8px;
    font-size: 1.2rem;
    cursor: pointer;
    touch-action: manipulation;
  }

  .scanner-actions {
    margin-top: 10px;
    display: flex;
    justify-content: center;
  }

  .scan-btn {
    background: #0077cc;
    color: white;
    border: none;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 1rem;
    cursor: pointer;
    touch-action: manipulation;
  }

  .stop-btn {
    background: #ff9800;
    color: white;
    border: none;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 1rem;
    cursor: pointer;
    touch-action: manipulation;
  }

  .qr-reader {
    width: 100%;
    max-width: 400px;
    margin-top: 1rem;
    transform: scaleX(-1); /* mirrors horizontally */
    border: 2px solid #0077cc;
    border-radius: 8px;
  }

  .face-page {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  video {
    width: 480px;
    border: 2px solid #0077cc;
    border-radius: 8px;
    transform: scaleX(-1); /* mirrors horizontally */
    margin-top: 1rem;
  }

  .preview img {
    max-width: 300px;
    border: 2px solid #0077cc;
    border-radius: 8px;
    margin-top: 10px;
  }

  button {
    margin: 1rem 0;
    padding: 12px 24px;
    font-size: 1.2rem;
    border-radius: 8px;
    border: none;
    background: #0077cc;
    color: white;
    cursor: pointer;
    touch-action: manipulation;
  }
  .login-result {
    margin-top: 20px;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .login-result img {
    width: 60px;
    height: 60px;
    border-radius: 8px;
    object-fit: cover;
    border: 2px solid #ccc;
  }

  .login-message {
    font-size: 1.2rem;
    font-weight: bold;
  }

  video {
    width: 100%;
    max-width: 480px;
    border-radius: 8px;
  }
  .camera-video {
    width: 100%;
    height: 100%;
    max-width: 600px;
    max-height: 1024px;
    object-fit: cover;         /* fills screen, keeps proportion */
    border: none;
    border-radius: 0;
    background: #000;
    display: block;
    margin: 0;
  }

  .settings-auth, .settings-page {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
    max-width: 400px;
    background: #fff;
    padding: 2rem;
    border-radius: 10px;
    box-shadow: 0 0 10px rgba(0,0,0,0.1);
    margin-top: 2rem;
  }

  .settings-auth input {
    width: 100%;
    padding: 10px;
    margin: 8px 0;
    font-size: 1rem;
  }

  .settings-page input {
    width: 100%;
    padding: 10px;
    font-size: 1rem;
    margin-top: 0.5rem;
  }
  .settings-page label {
    width: 100%;
    font-size: 1.1rem;
    margin-bottom: 1rem;
  }
  .settings-btn {
    position: absolute;
    bottom: 200px; 
    right: 30px;        
    width: 50px;        /* smaller for touch screens */
    height: 50px;
    font-size: 1.6rem;
    border: none;
    border-radius: 50%;
    background-color: #444;
    color: white;
    cursor: pointer;
    box-shadow: 0 4px 8px rgba(0,0,0,0.25);
    transition: background 0.2s, transform 0.2s;
    z-index: 1000;      /* ensure it stays above all other UI */
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.8rem;
    line-height: 1; /* removes weird emoji spacing */
    padding: 0; 
    touch-action: manipulation;
  }
  .settings-btn:hover {
    background-color: #222;
    transform: rotate(30deg);
  }
  .gear {
    display: inline-block;
    transform: translate(1px, 0px);/* 🔧 move the gear downward a bit */
  }

</style>