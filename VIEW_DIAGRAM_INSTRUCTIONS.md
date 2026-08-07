# How to View the ER Diagram

## Method 1: Online PlantUML Viewer
1. Go to [PlantUML Online Editor](https://www.plantuml.com/plantuml/uml/)
2. Copy the entire contents of `ER_DIAGRAM.puml`
3. Paste it into the online editor
4. The diagram will be automatically generated on the right side

## Method 2: Install PlantUML Extension in VS Code
1. Open VS Code
2. Go to Extensions (Ctrl+Shift+X)
3. Search for "PlantUML"
4. Install the "PlantUML" extension by jebbs
5. After installation:
   - Open `ER_DIAGRAM.puml`
   - Right-click in the editor
   - Select "Preview Current Diagram"
   - Or use Alt+D to preview

## Method 3: Using PlantUML Command Line
1. Install Java (if not already installed)
   ```bash
   # Windows (using chocolatey)
   choco install openjdk
   
   # Linux
   sudo apt-get install default-jre
   
   # Mac
   brew install openjdk
   ```

2. Download PlantUML jar
   ```bash
   # Create a tools directory
   mkdir tools
   cd tools
   
   # Download PlantUML
   curl -o plantuml.jar https://sourceforge.net/projects/plantuml/files/latest/download
   ```

3. Generate the diagram
   ```bash
   # Generate PNG
   java -jar plantuml.jar ER_DIAGRAM.puml
   
   # Generate SVG
   java -jar plantuml.jar -tsvg ER_DIAGRAM.puml
   ```

## Method 4: Using Docker
If you have Docker installed:
```bash
# Pull PlantUML image
docker pull plantuml/plantuml

# Generate diagram
docker run --rm -v ${PWD}:/work plantuml/plantuml ER_DIAGRAM.puml
```

## Output Formats
The diagram can be generated in multiple formats:
- PNG (default)
- SVG (vector format, scalable)
- PDF
- ASCII art

To generate in different formats using command line:
```bash
# SVG format
java -jar plantuml.jar -tsvg ER_DIAGRAM.puml

# PDF format
java -jar plantuml.jar -tpdf ER_DIAGRAM.puml

# ASCII art
java -jar plantuml.jar -ttxt ER_DIAGRAM.puml
```

## Troubleshooting
1. If you get a GraphViz error:
   - Windows: `choco install graphviz`
   - Linux: `sudo apt-get install graphviz`
   - Mac: `brew install graphviz`

2. If the preview is not working in VS Code:
   - Ensure Java is installed and in PATH
   - Restart VS Code
   - Check the PlantUML extension settings

3. If the online viewer is slow:
   - Try using the local installation methods
   - Consider generating static images

## Additional Resources
- [PlantUML Official Documentation](https://plantuml.com/)
- [PlantUML Visual Studio Code Extension](https://marketplace.visualstudio.com/items?itemName=jebbs.plantuml)
- [PlantUML Docker Image](https://hub.docker.com/r/plantuml/plantuml/) 