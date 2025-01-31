// Function to read file and display its contents
async function processPackets() {
    const packetFileInput = document.getElementById('packet_file');
    const packetFile = packetFileInput.files[0];

    const xtceFileInput = document.getElementById('xtce_file');
    const xtceFile = xtceFileInput.files[0];

    if (!packetFile || !xtceFile) {
        alert('Please select a packet file and XTCE definition file');
        return;
    }

    const xtceArrayBuffer = await xtceFile.arrayBuffer();
    const xtceUint8Array = new Uint8Array(xtceArrayBuffer);

    const packetArrayBuffer = await packetFile.arrayBuffer();
    const packetUint8Array = new Uint8Array(packetArrayBuffer);

    // Setup our environment
    let pyodide = await loadPyodide();
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");
    await micropip.install('space_packet_parser');

    // Pass the binary file content to Python by setting a Python global variable
    pyodide.globals.set('packet_content', packetUint8Array);
    // also pass in the XTCE file content
    pyodide.globals.set('xtce_content', xtceUint8Array);

    // Execute Python code to simulate opening a binary file
    await pyodide.runPythonAsync(`
        import io
        from space_packet_parser.definitions import XtcePacketDefinition

        # Create an in-memory binary file using io.BytesIO
        packet_file_obj = io.BytesIO(packet_content.to_py())
        xtce_file_obj = io.BytesIO(xtce_content.to_py())
        packet_def = XtcePacketDefinition(xtce_file_obj)

        count = 0
        packet_generator = packet_def.packet_generator(packet_file_obj)
        packets = list(packet_generator)
        npackets = len(packets)
        print(f"Total packets: {npackets}")
    `);

   // Import the Python list back to JavaScript as an array of dictionaries
   const objectList = pyodide.globals.get('packets');
   const nPackets = pyodide.globals.get('npackets');

    // Display the list contents in the output div
    const outputDiv = document.getElementById('output');
    outputDiv.innerHTML = `<h4>Parsed ${nPackets} packets</h4>`;

    // Create a list in HTML to display each object
    const ol = document.createElement('ol');

    // Iterate through the objectList to append each item
    objectList.forEach(obj => {
        const li = document.createElement('li');
        li.textContent = `Packet: ${obj}`;
        ol.appendChild(li);
    });

    // Append the list to the output div
    outputDiv.appendChild(ol);
}

// Add event listener to process button
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('process').addEventListener('click', processPackets);
});
