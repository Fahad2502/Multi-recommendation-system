

// --- Movie Detail Modal ---
async function showMovieDetails(movieId) {
  // show placeholder
  const modalBody = document.getElementById('movieDetailContent');
  modalBody.innerHTML = `
      <h4>Loading...</h4>
      <p><strong>Overview:</strong></p>
      <p><strong>Rating:</strong></p>
      <p><strong>Release Date:</strong></p>
      <h5 class="mt-4">🎥 Trailer</h5>
      <div class="text-muted">Fetching trailer...</div>
      <h5 class="mt-4">🎭 Cast</h5>
      <div class="d-flex text-muted">Fetching cast...</div>
  `;
  new bootstrap.Modal(document.getElementById('movieDetailModal')).show();

  try {
    const res = await fetch(`/movie-details/${movieId}`);
    const data = await res.json();

    console.log("movie-details response:", data); // ✅ debug

    const castHtml = (data.cast || []).map(actor => `
      <div class="text-center me-3">
        <img src="${actor.profile}" class="rounded-circle" style="width: 80px; height: 80px; object-fit: cover;">
        <p class="mt-2">${actor.name}</p>
      </div>
    `).join('');

    const trailerIframe = data.trailer
      ? `<iframe width="100%" height="315" src="https://www.youtube.com/embed/${data.trailer}" frameborder="0" allowfullscreen></iframe>`
      : `<p class="text-muted">No trailer available.</p>`;

    modalBody.innerHTML = `
      <h4>${data.title || "Unknown title"}</h4>
      <p><strong>Overview:</strong> ${data.overview || "No overview"}</p>
      <p><strong>Rating:</strong> ⭐ ${data.rating ?? "N/A"} / 10</p>
      <p><strong>Release Date:</strong> ${data.release || "N/A"}</p>
      <h5 class="mt-4">🎥 Trailer</h5>
      ${trailerIframe}
      <h5 class="mt-4">🎭 Cast</h5>
      <div class="d-flex">${castHtml}</div>
    `;
  } catch (err) {
    console.error("movie-details error:", err);
    modalBody.innerHTML = `<p class="text-danger">Failed to load details.</p>`;
  }
}

// --- Fetch recommendations ---
async function getRecommendations() {
  const movie = document.getElementById("searchInput").value;
  if (!movie.trim()) {
    alert("Please enter a movie name!");
    return;
  }

  const spinner = document.getElementById("loadingSpinner");
  spinner.style.display = "block";

  try {
    const response = await fetch("/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ movie })
    });

    if (!response.ok) {
      const text = await response.text();
      console.error("recommend error status:", response.status, text);
      alert("Server error while fetching recommendations.");
      return;
    }

    const data = await response.json();
    console.log("recommend response:", data); // ✅ debug

    // render movies
    const movieList = document.getElementById("movieList");
    movieList.innerHTML = "";
    (data.movies || []).forEach(m => {
      movieList.innerHTML += `
        <div class="col">
          <div class="card h-100 fade-in">
            <img src="${m.poster || 'https://via.placeholder.com/300x450'}"
                 class="card-img-top"
                 alt="${m.title}"
                 style="height: 200px; object-fit: cover;"
                 title="${m.title}"
                 onclick="showMovieDetails(${m.id})">
            <div class="card-body">
              <h5 class="card-title text-white fw-bold">${m.title}</h5>
            </div>
          </div>
        </div>
      `;
    });

    renderMusic(data.music || []);
    renderBooks(data.books || []);

  } catch (err) {
    console.error("recommend fetch failed:", err);
    alert("Could not fetch recommendations.");
  } finally {
    spinner.style.display = "none";
  }
}

// --- Render music cards ---
function renderMusic(musicData) {
  const container = document.getElementById("musicContainer");
  container.innerHTML = "";
  musicData.forEach(music => {
    const card = document.createElement("div");
    card.className = "col";
    card.innerHTML = `
      <div class="card h-100 shadow-sm">
        <img src="${music.image || 'https://via.placeholder.com/150'}" class="card-img-top" alt="${music.artist || 'Artist'}">
        <div class="card-body">
          <h5 class="card-title">${music.artist || "Unknown Artist"}</h5>
          <p class="card-text"><strong>Rating:</strong> ${music.rating ?? "N/A"}</p>
          <p class="card-text">${music.description || ""}</p>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

// --- Render book cards ---
function renderBooks(books) {
  const container = document.getElementById("bookList");
  container.innerHTML = "";
  books.forEach(book => {
    const card = document.createElement("div");
    card.className = "col";
    card.innerHTML = `
      <div class="card h-100 shadow-sm">
        <img src="${book.thumbnail || book.image || 'https://via.placeholder.com/150'}" class="card-img-top" alt="${book.title || 'Book'}">
        <div class="card-body">
          <h5 class="card-title">${book.title || "Untitled"}</h5>
          <p class="card-text"><strong>Author:</strong> ${(book.authors && book.authors.join(', ')) || book.author || "Unknown"}</p>
          <p class="card-text"><strong>Genre:</strong> ${book.genre || "N/A"}</p>
          <p class="card-text"><strong>Rating:</strong> ${book.rating ?? "N/A"}</p>
          <p class="card-text">${book.description || ""}</p>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}


// If your HTML uses onclick="getRecommendations()" and onclick="showMovieDetails(id)",
// make sure these functions are on window (global).
window.getRecommendations = getRecommendations;
window.showMovieDetails = showMovieDetails;
