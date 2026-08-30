Project Alice

Overview
Alice is an anime inspired personal AI assistance / LLM / animatronic project. She listens and remembers your conversations. It combines Ollama's LLM model, conversational AI, voice interaction using FishAudio, memory, research tools, and a 3D avatar. In the process of developing and designing an animatronic body for Alice that would serve as a physical companion and therapist for individuals who are unable to meet with therapists and counselors on a regular basis while also serving as an educational tool for learning multiple languages such as Japanese. She is being developed as a desktop / web experience, IOS companion app, and eventually a physical PLA / 3D printed animatronic with servo motor controlled movement. 

Features
- Conversation history and memory file to recall previous conversations
- Voice generation using FishAudio for English and VoiceVox for Japanese
- Text-to-speech and speech recognition
- iOS app and web server interface
- VRM/GLTF avatar model
- Research and assistant tools such as a to-do list and self-improving code using proposals and manual approval 
- iOS companion app
- Support for therapeutic and self-improvement flows

Project structure 
- alice.py                         # main Alice assistant and backend logic
- alice_self_improvement.py        # proposal, approval, and safe imporvement system that allows Alice to add to her own code / tools
- alice_code_editor.py             # tools / interface that allow Alice to review / edit her own code
- fluctlight.html                  # web viewer for VRM / GLTF avatar
- requirements.txt                 # python package dependencies
- package.json                     # JavaScript dependencies
- ios/                             # Xcode project and iOS app source files
- assets/                          # models, audio, images and other project assets 

Requirements
- Python 3.11 or older
- pip
- Node.js and npm for the web avatar viewer
- XCode when building the iOS app
- iPhone / IOS simulator for mobile testing
- API keys for any AI, text-to-speech, speech recognition, research, or Spotify media control

Goals 
- Make Alice into a supportive and expressive AI compnanion capable of communicating through text, voice, and physical movement. The project is designed with user control in mind, allowing users to manage Alice's behavior, memory, and future capabilities.

Project Status 
- Alice is currently under development. Features and interfaces may change as the project evolves. Designed preliminary CAD model for physical animatronic body, including joints, limbs, head and torso
using a combination of Fusion 360 and Blender, programmed main core functionality of therapist model using a large language learning model (LLM) in Python with computer vision integration via OpenCV, supporting standard image identification, Japanese to English translation, speech recognition, and additional
features. Currently working on iOS app.

Hardware Roadmap
Alice is planned to grow into a physical animatronic prototype built from 3D-printed PLA components and servo motors, including 
- Head and neck movement
- Eye, eyelid, and facial-expression mechanisms
- Mouth movement synchronized with speech
- Servo control connected to Alice's responses
- Wiring enclosure
- Movement that reflects Alice's speaking and emotional state 

OpenCV Demo Video: 
https://www.youtube.com/watch?v=Jtboe6DYDfQ

Future Plans 
- Memory synthesis to create core memories between user and Alice in the form of a mind map to show Alice's thoughts / memories in real time
- Time/location awareness
- Improve linguistic deflection and add additional languages such as Spanish
- Hand tracking / gesture control over the Alice interface
- Self-improving model using AWS code whisperer
- Adaptive emotion / physical movement generator
- Exercise / choreography simulator
- Gaming companion, giving Alice complete control over the Chrome web browser so that she can play games with you
- Time stamping / log sessions and generate notes based on sessions with user
- Goal / context/ planning / feedback control loop
