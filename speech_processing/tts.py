from gtts import gTTS
import os

def text_to_speech_google(text, output_file="output.mp3", language="en"):
    """
    Convert text to speech using Google Text-to-Speech API
    
    Parameters:
        text: The text to convert to speech
        output_file: Path to save the audio file
        language: Language code (e.g., 'en' for English, 'fr' for French)
    """
    # Create gTTS object
    tts = gTTS(text=text, lang=language, slow=False)
    
    # Save to file
    tts.save(output_file)
    
    # Play the audio (works on most platforms)
    os.system(f"start {output_file}" if os.name == "nt" else f"open {output_file}")
    
    print(f"Audio saved to {output_file}")
    return output_file

# Example usage
if __name__ == "__main__":
    sample_text = "Hello, this is a text to speech conversion example using Google's API."
    text_to_speech_google(sample_text)