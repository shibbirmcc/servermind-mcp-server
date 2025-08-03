const fs = require('fs');
const path = require('path');

describe('README.md', () => {
  let readmeContent;

  beforeAll(() => {
    const readmePath = path.join(__dirname, '..', 'README.md');
    readmeContent = fs.readFileSync(readmePath, 'utf8');
  });

  test('should exist', () => {
    expect(readmeContent).toBeDefined();
    expect(readmeContent.length).toBeGreaterThan(0);
  });

  test('should have proper title', () => {
    expect(readmeContent).toContain('# Splunk MCP Server');
  });

  test('should contain overview section', () => {
    expect(readmeContent).toContain('## Overview');
  });

  test('should contain features section', () => {
    expect(readmeContent).toContain('## Features');
    expect(readmeContent).toContain('### Current Capabilities');
    expect(readmeContent).toContain('### Planned Features');
  });

  test('should contain installation instructions', () => {
    expect(readmeContent).toContain('## Installation');
    expect(readmeContent).toContain('### Prerequisites');
    expect(readmeContent).toContain('### Setup');
  });

  test('should contain configuration section', () => {
    expect(readmeContent).toContain('## Configuration');
    expect(readmeContent).toContain('config.json');
  });

  test('should contain usage examples', () => {
    expect(readmeContent).toContain('## Usage');
    expect(readmeContent).toContain('### Available Tools');
    expect(readmeContent).toContain('splunk_search');
  });

  test('should contain security considerations', () => {
    expect(readmeContent).toContain('## Security Considerations');
  });

  test('should contain development section', () => {
    expect(readmeContent).toContain('## Development');
    expect(readmeContent).toContain('### Project Structure');
  });

  test('should contain troubleshooting section', () => {
    expect(readmeContent).toContain('## Troubleshooting');
    expect(readmeContent).toContain('### Common Issues');
  });

  test('should contain proper GitHub repository references', () => {
    expect(readmeContent).toContain('shibbirmcc/splunk-mcp-server');
  });

  test('should contain license information', () => {
    expect(readmeContent).toContain('## License');
    expect(readmeContent).toContain('MIT License');
  });

  test('should contain changelog', () => {
    expect(readmeContent).toContain('## Changelog');
    expect(readmeContent).toContain('v1.0.0');
  });

  test('should reference Python as primary language', () => {
    expect(readmeContent).toContain('Python 3.8+');
    expect(readmeContent).toContain('python src/server.py');
    expect(readmeContent).toContain('requirements.txt');
    expect(readmeContent).toContain('pyproject.toml');
  });

  test('should contain Python project structure', () => {
    expect(readmeContent).toContain('server.py');
    expect(readmeContent).toContain('client.py');
    expect(readmeContent).toContain('__init__.py');
    expect(readmeContent).toContain('python -m pytest tests/');
  });
});
