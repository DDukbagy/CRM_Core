const { getDefaultConfig } = require("expo/metro-config");
const path = require("path");

const projectRoot = __dirname;
const workspaceRoot = path.resolve(projectRoot, "../..");

const config = getDefaultConfig(projectRoot);

// 모노레포: 공유 packages만 추가 감시 (backend, frontend 제외)
config.watchFolders = [path.resolve(workspaceRoot, "packages")];

// node_modules 탐색 순서: 앱 → 워크스페이스 루트
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, "node_modules"),
  path.resolve(workspaceRoot, "node_modules"),
];

module.exports = config;
