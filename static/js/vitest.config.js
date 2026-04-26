import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.js'],
    include: ['tests/**/*.test.js'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      thresholds: {
        lines: 90,
        functions: 90,
        branches: 90,
        statements: 90
      },
      include: ['utils/**/*.js', 'core/**/*.js', 'commands/**/*.js', 'modules/**/*.js'],
      exclude: ['**/libs/SocketIoMin.js', '**/tests/**']
    },
    testTimeout: 10000,
    hookTimeout: 10000
  }
});
