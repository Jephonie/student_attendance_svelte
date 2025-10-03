<script>
  import { onMount } from "svelte";

  // UI state
  let showForm = false;
  let showFacePage = false;
  let showLoginPage = false;

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

  let loginVideo;
  let loginCanvas;
  let loginCtx;
  let loginStream;
  let loginCamera = null;
  let loginMessage = "";
  let loginMessageColor = "black"; 
  let detectionInterval;
  let loginImageUrl = "";

  const SERVER_URL = "http://your-server-ip:3000";

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
    const ctx = canvas.getContext("2d");

    // target size for FaceAPI detection
    const TARGET_WIDTH = 640;
    const TARGET_HEIGHT = 480;

    canvas.width = TARGET_WIDTH;
    canvas.height = TARGET_HEIGHT;

    // draw scaled image from video
    ctx.drawImage(video, 0, 0, TARGET_WIDTH, TARGET_HEIGHT);

    return canvas.toDataURL("image/jpeg");
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
      console.log("Starting camera with selectedCamera:", selectedCamera);
      // use ideal to avoid failing if exact deviceId isn't usable
      const constraints = {
        video: {
          deviceId: faceCamera ? { exact: faceCamera } : { exact: selectedCamera },
          width: { ideal: 1280 },
          height: { ideal: 720 }
        }
      };
      stream = await navigator.mediaDevices.getUserMedia(constraints);
      video.srcObject = stream;
      await video.play();
      console.log("Camera started");
      // ensure ctx
      if (!ctx && canvas) ctx = canvas.getContext("2d");

      autoCaptureSequence();
    } catch (err) {
      console.error("Camera start error:", err);
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
        console.log("Orientation:", orientation);

        if (faceStep === 1 && orientation === "front") captured = true;
        if (faceStep === 2 && orientation === "right") captured = true;
        if (faceStep === 3 && orientation === "left") captured = true;

        if (captured) {
          const frame = takeSnapshot();
          capturedImages[`pic${faceStep}`] = frame;
          console.log(`✅ Auto captured step ${faceStep}`);
          faceStep++;
          await new Promise(res => setTimeout(res, 1500)); // pause before next step
        }

        await new Promise(res => setTimeout(res, 500)); // polling interval
      }
    }

    // After all 3 captured → register
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
  }
  
  async function startLoginCamera() {
    try {
      // Dynamically find EMEET camera id
      const devices = await navigator.mediaDevices.enumerateDevices();
      const emeetCam = devices.find(
        d => d.kind === "videoinput" && (d.label || "").toLowerCase().includes("emeet")
      );

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
    if (!loginCtx || !loginVideo.videoWidth) return;

    loginCanvas.width = loginVideo.videoWidth;
    loginCanvas.height = loginVideo.videoHeight;
    loginCtx.drawImage(loginVideo, 0, 0, loginCanvas.width, loginCanvas.height);

    const imageData = loginCanvas.toDataURL("image/png");

    try {
      const res = await fetch("http://localhost:3000/detect-face", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: imageData })
      });

      const data = await res.json();

      if (data.faceDetected) {
        clearInterval(detectionInterval);
        await sendForRecognition(imageData);
      }
    } catch (err) {
      console.error("Detection error:", err);
    }
  }
  async function sendForRecognition(imageData) {
    try {
      const res = await fetch("http://localhost:3000/login-recognize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: imageData })
      });

      const data = await res.json();

      loginMessage = data.message;
      loginMessageColor = data.message.includes("Welcome") ? "green" : "red";
      loginImageUrl = data.imageUrl || ""; // 👈 save thumbnail URL

      stopLoginCamera();
    } catch (err) {
      console.error("Recognition error:", err);
      loginMessage = "❌ Error during recognition";
      loginMessageColor = "red";
      loginImageUrl = "";
      stopLoginCamera();
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
  }

</script>

<div class="screen">
  {#if !showForm && !showFacePage && !showLoginPage}
    <div class="main-buttons">
      <button class="big-btn" on:click={() => { showLoginPage = true; startLoginCamera(); }}>
        Login
      </button>
    </div>

    <div class="bottom-button">
      <button class="big-btn" on:click={() => showForm = true}>
        Register
      </button>
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

        <!-- Live camera -->
      <video bind:this={video} autoplay muted playsinline class="live-video"></video>


      <canvas bind:this={canvas} style="display:none"></canvas>

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
      <video bind:this={loginVideo} autoplay playsinline muted class="border rounded w-96 h-72"></video>
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

</div>

<style>
  .screen {
    width: 600px;
    height: 1024px;
    display: flex;
    flex-direction: column; 
    align-items: center;
    justify-content: center;
    background: #f9f9f9;
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
  }

  .stop-btn {
    background: #ff9800;
    color: white;
    border: none;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 1rem;
    cursor: pointer;
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
  .live-video {
    width: 320px;      /* or whatever size you want */
    border: 2px solid #000;
    border-radius: 8px;
  }

</style>