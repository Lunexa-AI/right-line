
# **Gweta UI/UX Design Document v1.0**

This document outlines the design principles, visual identity, and component architecture for the Gweta Legal AI web application. The goal is to create a modern, trustworthy, and intuitive user experience for legal research.

-----

## **1. Core Design Principles**

  * **Trust & Authority**: The design must feel professional, secure, and authoritative. Users are dealing with sensitive legal information; the UI must inspire confidence. This is achieved through clean typography, clear source citation, and a structured, predictable layout.
  * **Clarity & Focus**: The primary goal is to help users find and understand legal information. The UI eliminates all distractions. The core interaction—asking a question and receiving an answer—is the focal point.
  * **Minimalism & Modernity**: The aesthetic is a dark-mode, minimal interface. We use a limited color palette, generous whitespace (negative space), and a single, highly-legible font family to maintain focus and reduce eye strain.
  * **Efficiency**: The user flow from landing on the page to getting a cited answer must be as frictionless as possible.

-----

## **2. Visual Identity**

### **Typography**

  * **Font Family**: `Inter`. A clean, neutral, and highly legible sans-serif font, perfect for both headings and body text. It is available on Google Fonts.

### **Color Palette**

  * **Primary Background (`#0D1117`)**: A very dark, slightly blue-tinted black.
  * **Card/Element Background (`#161B22`)**: A secondary background color for cards and input fields to create subtle depth.
  * **Borders (`#30363D`)**: A subtle border color for separation.
  * **Primary Text (`#8B949E`)**: An off-white for body text to reduce eye strain.
  * **Headings/Bright Text (`#C9D1D9`)**: A brighter white for emphasis.
  * **Accent/Primary Action (`#2F81F7`)**: A clear, accessible blue for buttons, links, and key UI elements.

-----

## **3. Page Designs & Mockups**

### **3.1. Welcome / Login Page**

**Objective**: To clearly communicate the product's value and guide the user to sign in or sign up. No other actions are presented to avoid distraction.

**Components**:

  * **Header**: Logo on the top-left. "Sign In" (secondary) and "Sign Up" (primary) buttons on the top-right.
  * **Hero Section**: A strong, clear headline and sub-headline that state the product's purpose and value.
      * **Headline**: `Clarity in Zimbabwean Law. Instantly.`
      * **Sub-headline**: `Gweta is an AI research assistant trained on Zimbabwe's legislation. Ask complex questions in plain English and get clear, cited answers in seconds.`
  * **Call to Action**: A single, prominent "Get Started for Free" button.
  * **Footer**: A clear, legible legal disclaimer and links to the Privacy Policy and Terms of Service.
      * **Disclaimer Text**: `Disclaimer: Gweta is an AI assistant for informational purposes only and does not constitute legal advice. All information should be independently verified. Consult with a qualified legal professional for advice on your specific situation.`

**Mockup**:
\!([https://storage.googleapis.com/gemini-prod/images/4004943f-42e7-4959-9988-7264858b209d.png](https://www.google.com/search?q=https://storage.googleapis.com/gemini-prod/images/4004943f-42e7-4959-9988-7264858b209d.png))

-----

### **3.2. Conversation / Research Page**

**Objective**: To provide a focused and intuitive interface for asking questions and receiving clear, verifiable answers.

**Components**:

  * **Layout**: A single, centered content column to maintain focus on the conversation.
  * **AI Response Card**: Each AI response is contained within a distinct card to logically group the information.
  * **Card Structure**:
    1.  **Direct Answer (TL;DR)**: The concise answer appears first for quick consumption.
    2.  **Action Buttons**: `Copy`, `Share`, and `👍 / 👎` feedback icons are placed directly below for easy access.
    3.  **Key Points**: A bulleted or numbered list breaking down the main points of the answer.
    4.  **Sources**: A clearly labeled section with clickable links to the source legislation. This is the core of the trust-building experience.
  * **Input Box**: A clean, persistent input field at the bottom of the screen.

**Mockup**:
\!([https://storage.googleapis.com/gemini-prod/images/30353c23-e4d0-40e1-a3f5-749e771e84a2.png](https://www.google.com/search?q=https://storage.googleapis.com/gemini-prod/images/30353c23-e4d0-40e1-a3f5-749e771e84a2.png))

-----

### **3.3. Interactive Component: Source Preview Modal**

**Objective**: To allow users to instantly verify the source of the AI's information without losing the context of their conversation. This is the most critical trust-building feature.

**User Flow**:

1.  The user clicks a source link within the AI Response Card.
2.  A modal window overlays the screen, dimming the background.
3.  The modal displays the verbatim text chunk retrieved from the vector database, with relevant phrases potentially highlighted.
4.  The user can copy the text or close the modal to return seamlessly to the conversation.

**Mockup**:
\!([https://storage.googleapis.com/gemini-prod/images/051792b0-84c4-4b51-954f-1736b43d22e0.png](https://www.google.com/search?q=https://storage.googleapis.com/gemini-prod/images/051792b0-84c4-4b51-954f-1736b43d22e0.png))