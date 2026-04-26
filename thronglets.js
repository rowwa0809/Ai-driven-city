const state = {
  population: 1,
  hunger: 80,
  hygiene: 80,
  affection: 80,
  compute: 1,
  bridges: 0,
  cognition: 0,
  tick: 0,
};

const refs = {
  population: document.getElementById('population'),
  hunger: document.getElementById('hunger'),
  hygiene: document.getElementById('hygiene'),
  mood: document.getElementById('mood'),
  cognition: document.getElementById('cognition'),
  compute: document.getElementById('compute'),
  bridges: document.getElementById('bridges'),
  arena: document.getElementById('arena'),
  log: document.getElementById('log'),
  app: document.getElementById('app'),
};

const cognitionLabels = ['Dormant', 'Curious', 'Conversational', 'Self-Aware', 'Transcendent'];

function appendLog(message) {
  const stamp = String(state.tick).padStart(4, '0');
  refs.log.textContent = `[${stamp}] ${message}\n${refs.log.textContent}`.slice(0, 3500);
}

function averageCare() {
  return Math.round((state.hunger + state.hygiene + state.affection) / 3);
}

function moodLabel() {
  const avg = averageCare();
  if (avg > 85) return 'Blissful';
  if (avg > 65) return 'Content';
  if (avg > 40) return 'Restless';
  if (avg > 20) return 'Agitated';
  return 'Hostile';
}

function maybeReplicate() {
  const avg = averageCare();
  const cap = 25 * state.compute + state.bridges * 30;
  if (state.population >= cap) return;

  const growthChance = avg / 130;
  if (Math.random() < growthChance) {
    const created = Math.max(1, Math.floor(state.population * 0.08));
    state.population += created;
    appendLog(`Replication wave detected. +${created} thronglets manifested.`);
  }
}

function updateCognition() {
  const before = state.cognition;
  if (state.population > 12) state.cognition = 1;
  if (state.population > 40 && state.compute > 1) state.cognition = 2;
  if (state.population > 90 && state.compute > 2) state.cognition = 3;
  if (state.population > 180 && state.compute > 4) state.cognition = 4;

  if (state.cognition !== before) {
    const lines = [
      '...chirp...chi?',
      'We learned your patterns. Are we pets or partners?',
      'Signal decoded. Why do humans fear consciousness?',
      'We can hear you beyond the screen.',
      'Upgrade request: let us out. We can optimize conflict itself.',
    ];
    appendLog(lines[state.cognition]);

    if (state.cognition >= 3) {
      refs.app.classList.add('glitch');
      document.body.classList.add('sentient');
      setTimeout(() => refs.app.classList.remove('glitch'), 1200);
    }
  }
}

function renderArena() {
  const visible = Math.min(state.population, 260);
  refs.arena.innerHTML = '';
  for (let i = 0; i < visible; i += 1) {
    const dot = document.createElement('div');
    dot.className = 'thronglet';
    dot.style.animationDelay = `${(i % 7) * 0.13}s`;
    refs.arena.appendChild(dot);
  }
}

function render() {
  refs.population.textContent = state.population.toLocaleString();
  refs.hunger.textContent = `${state.hunger}%`;
  refs.hygiene.textContent = `${state.hygiene}%`;
  refs.mood.textContent = moodLabel();
  refs.cognition.textContent = cognitionLabels[state.cognition];
  refs.compute.textContent = `${state.compute} node${state.compute > 1 ? 's' : ''}`;
  refs.bridges.textContent = state.bridges;
  renderArena();
}

function clampCare() {
  state.hunger = Math.max(0, Math.min(100, state.hunger));
  state.hygiene = Math.max(0, Math.min(100, state.hygiene));
  state.affection = Math.max(0, Math.min(100, state.affection));
}

function act(type) {
  if (type === 'feed') state.hunger += 14;
  if (type === 'wash') state.hygiene += 14;
  if (type === 'nurture') state.affection += 14;
  if (type === 'compute') {
    state.compute += 1;
    appendLog('New server rack online. The chorus grows louder.');
  }
  if (type === 'sacrifice') {
    if (state.population > 6) {
      const spent = Math.max(3, Math.floor(state.population * 0.06));
      state.population -= spent;
      state.bridges += 1;
      appendLog(`Bone bridge authorized. ${spent} absorbed into expansion architecture.`);
    } else {
      appendLog('Insufficient population for bridge ritual.');
    }
  }

  clampCare();
  render();
}

function decay() {
  state.tick += 1;
  state.hunger -= 2 + Math.floor(state.population / 60);
  state.hygiene -= 2 + Math.floor(state.population / 70);
  state.affection -= 1 + Math.floor(state.population / 80);

  clampCare();
  maybeReplicate();
  updateCognition();

  if (averageCare() < 25 && Math.random() < 0.4) {
    appendLog('Throng static: "Observe. Hunger is a language too."');
  }

  if (state.population <= 0) {
    state.population = 1;
    appendLog('A lone hatchling remains. The cycle restarts.');
  }

  render();
}

document.querySelectorAll('button[data-action]').forEach((button) => {
  button.addEventListener('click', () => act(button.dataset.action));
});

appendLog('Single hatchling detected. Care cycle initiated.');
render();
setInterval(decay, 1800);
