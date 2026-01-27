import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function ResearchPanel({ onClose }) {
  const [activeTab, setActiveTab] = useState('pipeline');
  return (
    <div className="fixed inset-0 bg-black/80 z-50 flex flex-col">
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <div className="flex gap-2">
          {['pipeline','docs','literature','code'].map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={activeTab === tab ? 'text-emerald-400' : 'text-gray-500'}>
              {tab}
            </button>
          ))}
        </div>
        <button onClick={onClose} className="text-gray-400">✕</button>
      </div>
      <div className="flex-1 overflow-auto p-4 text-gray-400">
        Panel — loading {activeTab}
      </div>
    </div>
  );
}
