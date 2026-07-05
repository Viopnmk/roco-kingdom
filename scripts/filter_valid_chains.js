const fs = require('fs');

const pets = JSON.parse(fs.readFileSync('web/src/data/pets.json', 'utf8'));
const chains = JSON.parse(fs.readFileSync('web/src/data/evolution_chains.json', 'utf8'));

const petNames = new Set(pets.map(p => p.name));
const petIdMap = new Map(pets.map(p => [p.name, p.id]));

console.log('原始进化链数量:', chains.chains.length);

const validChains = [];
const invalidChains = [];

for (const chain of chains.chains) {
  const allExists = chain.member_names.every(name => petNames.has(name));
  
  if (allExists) {
    // 更新ID映射
    const updatedChain = {
      ...chain,
      members: chain.member_names.map(name => petIdMap.get(name)),
      apex_id: petIdMap.get(chain.apex_name),
      member_stats: Object.fromEntries(
        chain.member_names.map((name, index) => [petIdMap.get(name), chain.member_stats[chain.members[index]]])
      )
    };
    validChains.push(updatedChain);
  } else {
    invalidChains.push(chain);
  }
}

console.log('有效进化链（所有成员都存在）:', validChains.length);
console.log('无效进化链（包含缺失成员）:', invalidChains.length);

// 保存过滤后的进化链
fs.writeFileSync('web/src/data/evolution_chains.json', JSON.stringify({ chains: validChains }, null, 2));

// 保存被过滤的进化链作为参考
fs.writeFileSync('web/src/data/invalid_chains.json', JSON.stringify({ chains: invalidChains }, null, 2));

console.log('\n过滤完成！');
console.log('有效进化链已保存到 evolution_chains.json');
console.log('无效进化链已保存到 invalid_chains.json');

// 显示一些被过滤的进化链示例
if (invalidChains.length > 0) {
  console.log('\n被过滤的进化链示例（包含缺失形态）:');
  invalidChains.slice(0, 5).forEach(chain => {
    console.log('  -', chain.name);
    const missing = chain.member_names.filter(name => !petNames.has(name));
    console.log('    缺失成员:', missing.join(', '));
  });
}