// pltr's helper for `pltr osdk generate` (#220): runs @osdk/foundry-sdk-generator
// without putting the Foundry token on a command line.
//
//   PLTR_OSDK_TOKEN=<token> node osdk_generate.mjs <install-dir> generatePackage [--option=value ...]
//
// The generator's command line takes the token only as --authToken, which
// anyone who can list processes can read. This script imports the generator's
// library entry point from <install-dir> (where pltr installed the pinned
// version with npm) and calls its exported cli(argv) in this process, adding
// --authToken in memory. The token comes from the PLTR_OSDK_TOKEN environment
// variable, which is deleted before the generator runs. pltr passes every
// other argument as given.
import { createRequire } from "node:module";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const TOKEN_ENV_VAR = "PLTR_OSDK_TOKEN";
const GENERATOR = "@osdk/foundry-sdk-generator";

const [installDir, ...args] = process.argv.slice(2);
const token = process.env[TOKEN_ENV_VAR];
delete process.env[TOKEN_ENV_VAR];

function fail(message) {
  process.stderr.write(`osdk_generate.mjs: ${message}\n`);
  process.exit(2);
}

if (!installDir || args.length === 0) {
  fail("usage: node osdk_generate.mjs <install-dir> generatePackage [--option=value ...]");
}
if (args.some((arg) => arg === "--authToken" || arg.startsWith("--authToken="))) {
  fail(`pass the token in ${TOKEN_ENV_VAR}, never as --authToken`);
}
if (!token) {
  fail(`${TOKEN_ENV_VAR} is not set: pltr passes the Foundry token in it`);
}

// Resolve the generator the way Node would from <install-dir>, through its
// package.json "exports".
const require = createRequire(join(installDir, "package.json"));
const { cli } = await import(pathToFileURL(require.resolve(GENERATOR)).href);

// cli() reads its arguments like process.argv: it skips the first two.
await cli([process.argv[0], "foundry-sdk-generator", ...args, `--authToken=${token}`]);
