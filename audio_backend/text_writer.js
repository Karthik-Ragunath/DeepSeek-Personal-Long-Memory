const fs = require('fs');
const path = require('path');

// Function to write text to a file
function writeTextToFile(text, filename = 'submitted_text.txt') {
  const filePath = path.join(__dirname, filename);
  
  try {
    // Write the text to the file
    fs.writeFileSync(filePath, text);
    console.log(`Successfully wrote text to: ${filePath}`);
    return true;
  } catch (error) {
    console.error(`Error writing to file: ${error.message}`);
    return false;
  }
}

// If this script is run directly from command line
if (require.main === module) {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.log('Usage: node text_writer.js "Your text here"');
    process.exit(1);
  }
  
  const textToWrite = args[0];
  const success = writeTextToFile(textToWrite);
  
  if (success) {
    console.log('Text has been saved successfully!');
  } else {
    console.log('Failed to save text.');
  }
}

// Export the function for use in other files
module.exports = { writeTextToFile }; 