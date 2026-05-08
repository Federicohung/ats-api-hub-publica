const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const docs = path.join(root, "docs");

fs.mkdirSync(docs, { recursive: true });

const copies = [
  ["index.html", "docs/index.html"],
  ["scraper/data/jobs.json", "docs/jobs.json"],
];

for (const [from, to] of copies) {
  const source = path.join(root, from);
  const target = path.join(root, to);
  if (!fs.existsSync(source)) {
    if (to.endsWith("jobs.json") && !fs.existsSync(target)) {
      fs.writeFileSync(
        target,
        JSON.stringify({ version: "1.0", schema: "api-aggregator", totalJobs: 0, sources: {}, categories: {}, jobs: [] }, null, 2)
      );
    }
    continue;
  }
  fs.copyFileSync(source, target);
}

console.log("Static build ready in docs/");
