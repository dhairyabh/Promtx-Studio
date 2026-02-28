document.addEventListener("DOMContentLoaded", () => {
  // ========== DOM ELEMENTS ==========
  const processBtn = document.getElementById("processBtn");
  const fileInput = document.getElementById("video");
  const promptInput = document.getElementById("prompt");
  const voiceBtn = document.getElementById("voiceBtn");
  const resultVideo = document.getElementById("resultVideo");
  const root = document.documentElement;
  const themeBtn = document.getElementById("themeToggle");
  const themeIcon = document.getElementById("themeIcon");

  // ========== THEME TOGGLE ==========
  if (themeBtn && themeIcon) {
    function applyTheme(theme) {
      root.setAttribute("data-theme", theme);
      localStorage.setItem("theme", theme);
      themeIcon.textContent = theme === "dark" ? "☀️" : "🌙";
      themeBtn.title = theme === "dark" ? "Switch to Light" : "Switch to Dark";
    }

    const saved = localStorage.getItem("theme") || "light";
    applyTheme(saved);

    themeBtn.addEventListener("click", () => {
      const current = root.getAttribute("data-theme") || "light";
      applyTheme(current === "light" ? "dark" : "light");
    });
  }

  // ========== VOICE RECOGNITION ==========
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition && voiceBtn) {
    const recognition = new SpeechRecognition();

    // Enhanced accuracy settings
    recognition.continuous = false;  // Automatically stop when user stops speaking
    recognition.lang = 'en-US';
    recognition.interimResults = true;  // Show real-time transcription
    recognition.maxAlternatives = 3;  // Get multiple alternatives for better accuracy

    let finalTranscript = '';
    let isRecording = false;

    voiceBtn.addEventListener("click", () => {
      if (isRecording) {
        recognition.stop();
        isRecording = false;
      } else {
        finalTranscript = '';
        recognition.start();
        isRecording = true;
      }
    });

    recognition.onstart = () => {
      voiceBtn.classList.add("recording");
      voiceBtn.innerText = "🔴";
      promptInput.placeholder = "Listening... Speak now";
    };

    recognition.onend = () => {
      voiceBtn.classList.remove("recording");
      voiceBtn.innerText = "🎤";
      promptInput.placeholder = "Enter your prompt or use voice";
      isRecording = false;
    };

    recognition.onresult = (event) => {
      let interimTranscript = '';

      // Process all results for better accuracy
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;

        if (event.results[i].isFinal) {
          finalTranscript += transcript + ' ';
        } else {
          interimTranscript += transcript;
        }
      }

      // Update input with final + interim results
      promptInput.value = (finalTranscript + interimTranscript).trim();
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      voiceBtn.classList.remove("recording");
      voiceBtn.innerText = "🎤";
      isRecording = false;

      if (event.error === 'no-speech') {
        promptInput.placeholder = "No speech detected. Try again.";
      } else if (event.error === 'audio-capture') {
        promptInput.placeholder = "Microphone not found. Check permissions.";
      } else {
        promptInput.placeholder = "Error: " + event.error;
      }
    };
  } else if (voiceBtn) {
    voiceBtn.style.display = "none";
  }

  // ========== VIDEO PROCESSING ==========
  if (processBtn) {
    processBtn.addEventListener("click", async () => {
      if (!checkQuota()) return; // Block if quota exceeded

      const file = fileInput.files[0];
      const prompt = promptInput.value.trim();

      if (!file && !prompt) {
        resultVideo.innerHTML = `<p style="color: #ef4444;">❌ Please upload a video or enter a generation prompt.</p>`;
        return;
      }

      // If no file but there's a prompt, assume generation
      if (!file && prompt) {
        resultVideo.innerHTML = `<p style="color: #38bdf8;">🎬 Generating video from prompt... (Wait max 4 to 5 min)</p>`;
        processBtn.disabled = true;
        processBtn.innerText = "Generating...";

        const formData = new FormData();
        formData.append("prompt", prompt);

        try {
          const response = await fetch("/process-video/", {
            method: "POST",
            body: formData,
          });

          const data = await response.json();

          if (data.error) {
            resultVideo.innerHTML = `<p style="color: #ef4444;">❌ ${data.error}</p>`;
          } else {
            incrementUsageCount(); // Increment usage on successful generation
            resultVideo.innerHTML = `
              <p style="color: #22c55e;">✅ Video generated successfully!</p>
              <video controls>
                <source src="${data.video_url}" type="video/mp4">
              </video>
              ${createShareButtons(data.video_url)}
            `;
          }
        } catch (error) {
          resultVideo.innerHTML = `<p style="color: #ef4444;">❌ Error: ${error.message}</p>`;
        } finally {
          processBtn.disabled = false;
          processBtn.innerText = "Process Video";
        }
        return;
      }

      // Otherwise, editing mode
      if (!prompt) {
        resultVideo.innerHTML = `<p style="color: #ef4444;">❌ Please enter a prompt.</p>`;
        return;
      }

      resultVideo.innerHTML = `<p style="color: #38bdf8;">⏳ Processing your video... (Wait max 4 to 5 min)</p>`;
      processBtn.disabled = true;
      processBtn.innerText = "Processing...";

      const formData = new FormData();
      formData.append("video", file);
      formData.append("prompt", prompt);

      try {
        const response = await fetch("/process-video/", {
          method: "POST",
          body: formData,
        });

        const data = await response.json();

        if (data.error) {
          resultVideo.innerHTML = `<p style="color: #ef4444;">❌ ${data.error}</p>`;
        } else if (data.summary) {
          resultVideo.innerHTML = `
            <div class="summary-box">
              <h3>📝 Summary</h3>
              <div class="summary-content">${data.summary}</div>
            </div>
          `;
        } else if (data.video_url && data.video_url.endsWith(".mp3")) {
          resultVideo.innerHTML = `
            <p style="color: #22c55e;">✅ Audio extracted successfully!</p>
            <audio controls>
              <source src="${data.video_url}" type="audio/mpeg">
            </audio>
          `;
        } else {
          resultVideo.innerHTML = `
            <p style="color: #22c55e;">✅ Video processed successfully!</p>
            <video controls>
              <source src="${data.video_url}" type="video/mp4">
            </video>
            ${createShareButtons(data.video_url)}
          `;
        }
      } catch (error) {
        resultVideo.innerHTML = `<p style="color: #ef4444;">❌ Error: ${error.message}</p>`;
      } finally {
        processBtn.disabled = false;
        processBtn.innerText = "Process Video";
      }
    });
  }

  // ========== FEEDBACK SYSTEM ==========
  const submitFeedbackBtn = document.getElementById("submitFeedback");
  if (submitFeedbackBtn) {
    submitFeedbackBtn.addEventListener("click", async () => {
      const nameInput = document.getElementById("userName");
      const emailInput = document.getElementById("userEmail");
      const messageInput = document.getElementById("userFeedback");
      const feedbackMessage = document.getElementById("feedbackMessage");

      const name = nameInput.value.trim();
      const email = emailInput.value.trim();
      const message = messageInput.value.trim();

      // Basic validation
      if (!name || !email || !message) {
        feedbackMessage.innerHTML = `<p style="color: #ef4444;">❌ Please fill in all fields.</p>`;
        return;
      }

      submitFeedbackBtn.disabled = true;
      submitFeedbackBtn.innerText = "Submitting...";
      feedbackMessage.innerHTML = ""; // Clear previous messages

      try {
        const response = await fetch("/api/feedback", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ name, email, message }),
        });

        const data = await response.json();

        if (data.error) {
          feedbackMessage.innerHTML = `<p style="color: #ef4444;">❌ ${data.error}</p>`;
        } else {
          // Success
          feedbackMessage.innerHTML = `<p style="color: #22c55e;">✅ ${data.message}</p>`;
          // Clear inputs
          nameInput.value = "";
          emailInput.value = "";
          messageInput.value = "";
        }
      } catch (error) {
        feedbackMessage.innerHTML = `<p style="color: #ef4444;">❌ Error submitting feedback. Please try again later.</p>`;
        console.error("Feedback error:", error);
      } finally {
        submitFeedbackBtn.disabled = false;
        submitFeedbackBtn.innerText = "Submit Feedback";
      }
    });
  }

  // ========== QUOTA MANAGEMENT ==========
  const quotaCountSpan = document.getElementById("quotaCount");
  const MAX_FREE_PROMPTS = 5;

  function getUsageCount() {
    return parseInt(localStorage.getItem("promptX_usage_count") || "0", 10);
  }

  function incrementUsageCount() {
    const current = getUsageCount();
    localStorage.setItem("promptX_usage_count", current + 1);
    updateQuotaUI();
  }

  function updateQuotaUI() {
    if (!quotaCountSpan) return;
    const current = getUsageCount();
    const remaining = Math.max(0, MAX_FREE_PROMPTS - current);

    quotaCountSpan.innerText = remaining;

    if (remaining === 0) {
      quotaCountSpan.parentElement.innerHTML = `<span style="color: #ef4444;">Free Trial Ended</span> • <a href="#subscription" style="color: var(--accent); text-decoration: underline;">Upgrade</a>`;
    }
  }

  function checkQuota() {
    if (getUsageCount() >= MAX_FREE_PROMPTS) {
      if (resultVideo) {
        resultVideo.innerHTML = `
          <div style="background: var(--soft); border: 1px solid var(--border); padding: 16px; border-radius: var(--radius); text-align: center;">
            <p style="font-size: 16px; font-weight: 800; color: #ef4444; margin-bottom: 8px;">🚀 Free Trial Ended</p>
            <p style="color: var(--text); font-size: 14px; margin-bottom: 12px;">You've used all 5 of your free trial prompts!</p>
            <a href="#subscription" style="display: inline-block; padding: 8px 16px; background: var(--accent); color: white; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 14px;">View Subscription Plans</a>
          </div>
        `;
      }
      return false; // Blocks operation
    }
    return true; // Allows operation
  }

  // Initialize Quota UI on load
  updateQuotaUI();

  // ========== CHATBOT WIDGET ==========
  const chatToggle = document.getElementById('chatToggle');
  const chatClose = document.getElementById('chatClose');
  const chatWindow = document.getElementById('chatWindow');
  const chatInput = document.getElementById('chatInput');
  const chatSend = document.getElementById('chatSend');
  const chatMessages = document.getElementById('chatMessages');

  if (chatToggle && chatWindow) {
    // Toggle window
    chatToggle.addEventListener('click', () => {
      chatWindow.classList.toggle('hidden');
      if (!chatWindow.classList.contains('hidden')) {
        chatInput.focus(); // Auto-focus input when opened
      }
    });

    chatClose.addEventListener('click', () => {
      chatWindow.classList.add('hidden');
    });

    // Helper: append message bubble
    function appendMessage(text, sender) {
      const msgDiv = document.createElement('div');
      msgDiv.classList.add('message', sender);

      const bubble = document.createElement('div');
      bubble.classList.add('bubble');

      // Basic formatting for bot lines (newlines to <br>)
      if (sender === 'bot') {
        bubble.innerHTML = text.replace(/\n/g, '<br>');
      } else {
        bubble.textContent = text;
      }

      msgDiv.appendChild(bubble);
      chatMessages.appendChild(msgDiv);
      chatMessages.scrollTop = chatMessages.scrollHeight; // Auto-scroll
      return msgDiv;
    }

    // Send Message
    async function sendMessage() {
      const text = chatInput.value.trim();
      if (!text) return;

      // 1. Show user message
      appendMessage(text, 'user');
      chatInput.value = '';

      // 2. Add 'typing...' indicator
      const typingMsg = appendMessage('Typing...', 'bot');
      chatSend.disabled = true;
      chatInput.disabled = true;

      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text })
        });

        const data = await response.json();

        // Remove typing indicator
        chatMessages.removeChild(typingMsg);

        if (data.reply) {
          appendMessage(data.reply, 'bot');
        } else {
          appendMessage('Sorry, I encountered an error answering that.', 'bot');
        }
      } catch (err) {
        chatMessages.removeChild(typingMsg);
        appendMessage('Error: Connection failed.', 'bot');
      } finally {
        chatSend.disabled = false;
        chatInput.disabled = false;
        chatInput.focus();
      }
    }

    chatSend.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') sendMessage();
    });
  }
});

