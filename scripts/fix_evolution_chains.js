const fs = require('fs');

const pets = JSON.parse(fs.readFileSync('web/src/data/pets.json', 'utf8'));
const chains = JSON.parse(fs.readFileSync('web/src/data/evolution_chains.json', 'utf8'));

const nameToId = new Map();
for (const pet of pets) {
  nameToId.set(pet.name, pet.id);
}

console.log('修复进化链ID映射问题:');
let fixedCount = 0;

for (const chain of chains.chains) {
  const oldMembers = [...chain.members];
  
  chain.members = chain.member_names.map(name => {
    const correctId = nameToId.get(name);
    if (correctId === undefined) {
      console.log('  警告: 未找到精灵 "' + name + '"');
      return null;
    }
    return correctId;
  }).filter(id => id !== null);
  
  const apexIndex = chain.member_names.indexOf(chain.apex_name);
  if (apexIndex >= 0 && apexIndex < chain.members.length) {
    chain.apex_id = chain.members[apexIndex];
  }
  
  const newStats = {};
  for (let i = 0; i < chain.member_names.length; i++) {
    const oldId = oldMembers[i];
    const newId = chain.members[i];
    if (newId !== undefined) {
      newStats[newId] = chain.member_stats[oldId];
    }
  }
  chain.member_stats = newStats;
  
  if (JSON.stringify(oldMembers) !== JSON.stringify(chain.members)) {
    fixedCount++;
    console.log('  修复: ' + chain.name + ' (' + oldMembers.join(',') + ' -> ' + chain.members.join(',') + ')');
  }
}

fs.writeFileSync('web/src/data/evolution_chains.json', JSON.stringify(chains, null, 2));
console.log('\n修复完成！共修复 ' + fixedCount + ' 个进化链');
