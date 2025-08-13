
import React from 'react';

import PopulationCard from './components/PopulationCard';
import CO2Card from './components/CO2Card';
import DeforestationCard from './components/DeforestationCard';
import TemperatureCard from './components/TemperatureCard';
import SmartphonesCard from './components/SmartphonesCard';
import InternetDataCard from './components/InternetDataCard';

import SpeciesExtinctionCard from './components/SpeciesExtinctionCard';

import PopulationChart from './components/PopulationChart';
import CO2Chart from './components/CO2Chart';
import DeforestationChart from './components/DeforestationChart';
import TemperatureChart from './components/TemperatureChart';
import SmartphonesChart from './components/SmartphonesChart';
import InternetDataChart from './components/InternetDataChart';
import SpeciesExtinctionChart from './components/SpeciesExtinctionChart';

function App() {
  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
      fontFamily: 'sans-serif',
      padding: 0,
      margin: 0
    }}>
      <div style={{
        maxWidth: 1200,
        margin: '0 auto',
        padding: '40px 16px 64px 16px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center'
      }}>
        <h1 style={{fontSize: 40, marginBottom: 8, color: '#222'}}>World Data View</h1>
        <p style={{fontSize: 20, color: '#444', marginBottom: 32}}>Bem-vindo à plataforma de dados globais!</p>
        <div style={{
          width: '100%',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: 32,
          justifyItems: 'center'
        }}>
          <PopulationCard />
          <CO2Card />
          <DeforestationCard />
          <TemperatureCard />
          <SmartphonesCard />
          <InternetDataCard />
          <SpeciesExtinctionCard />
        </div>
  <PopulationChart />
  <CO2Chart />
  <DeforestationChart />
  <TemperatureChart />
  <SmartphonesChart />
  <InternetDataChart />
  <SpeciesExtinctionChart />
      </div>
    </div>
  );
}

export default App;
