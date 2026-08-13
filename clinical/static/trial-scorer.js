(function (global) {
  "use strict";

  const TOKEN_PATTERN = /[a-z0-9_]{2,}/g;
  const CAPSTONE_WORDS = new Set([
    "anxiety", "arterial", "blood", "bone", "brain", "breast", "cancer", "cancers", "cardiac", "cardiovascular",
    "cholesterol", "depression", "diabetes", "diabetic", "electrocardiogram", "eye", "gastrointestinal", "heart", "immune", "infection",
    "infections", "infectious", "joint", "kidney", "lipid", "liver", "lung", "mental", "metabolic", "muscle",
    "muscles", "neurological", "obesity", "pain", "pediatric", "pregnancy", "prostate", "pulmonary", "renal", "respiratory",
    "sleep", "stroke", "therapy", "tumor", "tumors"
  ]);

  function murmurHash3(value, seed = 0) {
    const bytes = new TextEncoder().encode(value);
    const blockCount = Math.floor(bytes.length / 4);
    let hash = seed >>> 0;
    for (let index = 0; index < blockCount; index += 1) {
      const offset = index * 4;
      let block = bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16) | (bytes[offset + 3] << 24);
      block = Math.imul(block, 0xcc9e2d51);
      block = (block << 15) | (block >>> 17);
      block = Math.imul(block, 0x1b873593);
      hash ^= block;
      hash = (hash << 13) | (hash >>> 19);
      hash = (Math.imul(hash, 5) + 0xe6546b64) >>> 0;
    }
    let tail = 0;
    const tailOffset = blockCount * 4;
    switch (bytes.length & 3) {
      case 3: tail ^= bytes[tailOffset + 2] << 16;
      case 2: tail ^= bytes[tailOffset + 1] << 8;
      case 1:
        tail ^= bytes[tailOffset];
        tail = Math.imul(tail, 0xcc9e2d51);
        tail = (tail << 15) | (tail >>> 17);
        tail = Math.imul(tail, 0x1b873593);
        hash ^= tail;
    }
    hash ^= bytes.length;
    hash ^= hash >>> 16;
    hash = Math.imul(hash, 0x85ebca6b);
    hash ^= hash >>> 13;
    hash = Math.imul(hash, 0xc2b2ae35);
    hash ^= hash >>> 16;
    return hash | 0;
  }

  function sigmoid(value) {
    return value >= 0 ? 1 / (1 + Math.exp(-value)) : Math.exp(value) / (1 + Math.exp(value));
  }

  function normalize(text) {
    return String(text || "").toLocaleLowerCase().replace(/\s+/g, " ").trim();
  }

  function tokensFor(text) {
    return normalize(text).match(TOKEN_PATTERN) || [];
  }

  function featureKeys(text) {
    const tokens = tokensFor(text);
    const features = [];
    for (let index = 0; index < tokens.length; index += 1) {
      features.push(tokens[index]);
      if (index + 1 < tokens.length) features.push(`${tokens[index]} ${tokens[index + 1]}`);
    }
    return features;
  }

  function sentencesFor(text) {
    return String(text || "")
      .match(/[^.!?\n]+(?:[.!?]+|(?=\n|$))/g)
      ?.map((sentence) => sentence.replace(/\s+/g, " ").trim())
      .filter(Boolean) || [];
  }

  function capstoneWordContributions(text, wordScores) {
    return sentencesFor(text)
      .map((sentence) => {
        const observations = [...new Set(tokensFor(sentence))]
          .filter((term) => CAPSTONE_WORDS.has(term))
          .map((term) => ({ term, observation: wordScores[term] }))
          .filter(({ observation }) => observation);
        if (!observations.length) return null;
        return {
          phrase: sentence,
          delta: observations.reduce((total, { observation }) => total + Number(observation.lift) * 2, 0),
          detail: `Capstone word evidence: ${observations.map(({ term, observation }) => `${term}: ${(Number(observation.success_rate) * 100).toFixed(1)}% observed success, ${(Number(observation.lift) * 100).toFixed(1)} pp vs 50.0% baseline, embedding association ${Number(observation.assoc_score).toFixed(3)} across ${Number(observation.count)} source trials`).join("; ")}.`,
          source: "capstone_word"
        };
      })
      .filter(Boolean)
      .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta))
      .slice(0, 6);
  }

  function create(model) {
    const sparseWeights = model.sparse_weights || {};
    const baselines = model.baselines || {};
    const capstoneWordScores = model.capstone_word_scores?.data || {};

    function score(text, context = {}) {
      const normalized = normalize(text);
      const baselineKey = String(context.baselineKey || context.phase || "default").toLocaleLowerCase();
      const baseline = baselines[baselineKey] || baselines.default;
      let deltaLogit = 0;
      const contributions = [];

      for (const feature of featureKeys(normalized)) {
        const bucket = String(Math.abs(murmurHash3(feature)) % model.n_features);
        const weight = Number(sparseWeights[bucket] || 0);
        deltaLogit += weight;
      }

      const wordContributions = capstoneWordContributions(text, capstoneWordScores);
      for (const contribution of wordContributions) {
        deltaLogit += contribution.delta;
        contributions.push(contribution);
      }

      contributions.sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta));
      const logit = Number(baseline.base_logit) + deltaLogit;
      return {
        probability: sigmoid(logit),
        logit,
        deltaLogit,
        baselineKey: baselines[baselineKey] ? baselineKey : "default",
        baseline,
        contributions,
        modelType: model.model_type,
        modelVersion: model.version
      };
    }

    return { score, murmurHash3, model };
  }

  async function load(url = "/static/models/trial-language-signal.json?v=20260811-4") {
    const response = await fetch(url, { cache: "force-cache" });
    if (!response.ok) throw new Error("The local protocol language model could not be loaded.");
    const model = await response.json();
    const capstoneResponse = await fetch("/static/models/capstone-word-scores.json", { cache: "force-cache" });
    if (!capstoneResponse.ok) throw new Error("The local capstone word-score artifact could not be loaded.");
    model.capstone_word_scores = await capstoneResponse.json();
    return create(model);
  }

  global.TrialLanguageScorer = { create, murmurHash3, load };
})(window);