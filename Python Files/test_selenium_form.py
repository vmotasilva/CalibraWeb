#!/usr/bin/env python
"""
Test using Selenium to simulate real browser with authenticated session
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Start Chrome
print("🌐 Starting browser...")
driver = webdriver.Chrome()

try:
    # Navigate to the page
    print("📄 Loading historico page...")
    driver.get('http://localhost:8000/metrologia/historico/127/editar/')
    
    # Wait for page to load
    time.sleep(2)
    
    # Check if we're logged in (look for the form)
    try:
        form = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "carimboForm"))
        )
        print("✅ Page loaded successfully!")
    except:
        print("❌ Form not found, might not be logged in")
        print(f"Current URL: {driver.current_url}")
        print(f"Page title: {driver.title}")
    
    # Get form data
    resultado_field = driver.find_element(By.ID, "resultado_carimbo")
    data_field = driver.find_element(By.ID, "data_validacao_carimbo")
    validador_field = driver.find_element(By.ID, "nome_validador_carimbo")
    x_field = driver.find_element(By.ID, "carimbo_x")
    y_field = driver.find_element(By.ID, "carimbo_y")
    page_field = driver.find_element(By.ID, "carimbo_page")
    
    print("\n📋 Current form values:")
    print(f"  Resultado: {resultado_field.get_attribute('value')}")
    print(f"  Data: {data_field.get_attribute('value')}")
    print(f"  Validador: {validador_field.get_attribute('value')}")
    print(f"  X: {x_field.get_attribute('value')}")
    print(f"  Y: {y_field.get_attribute('value')}")
    print(f"  Page: {page_field.get_attribute('value')}")
    
    # Simulate a click on the canvas (if possible)
    canvas = driver.find_element(By.ID, "pdf-canvas")
    print(f"\n📍 Canvas size: {canvas.size}")
    
    # Click somewhere on the canvas
    from selenium.webdriver.common.action_chains import ActionChains
    action = ActionChains(driver)
    action.move_to_element_with_offset(canvas, 100, 100)
    action.click()
    action.perform()
    
    time.sleep(1)
    
    print("\n📍 After click:")
    print(f"  X: {x_field.get_attribute('value')}")
    print(f"  Y: {y_field.get_attribute('value')}")
    print(f"  Page: {page_field.get_attribute('value')}")
    
    # Now submit the form
    print("\n📝 Submitting form...")
    form = driver.find_element(By.ID, "carimboForm")
    form.submit()
    
    # Wait for response
    time.sleep(3)
    
    print(f"\n📊 After submit:")
    print(f"  Current URL: {driver.current_url}")
    print(f"  Page title: {driver.title}")
    
finally:
    driver.quit()
