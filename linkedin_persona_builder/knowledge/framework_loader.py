import yaml
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, validator
from orchestrator.config import settings
import logging
logger = logging.getLogger(__name__)


class CriterionData(BaseModel):
    name: str
    description: str
    question: str
    good_example: str
    bad_example: str
    threshold: float
    follow_up_example: str
    context_hints: list


class SectionData(BaseModel):
    name: str
    section_number: int
    objective: str
    estimated_time: str
    criteria: Dict[str, CriterionData]


class FrameworkMetadata(BaseModel):
    version: str
    total_sections: int
    estimated_time: str
    description: str
    objectives: list


class FrameworkData(BaseModel):
    metadata: FrameworkMetadata
    sections: Dict[str, SectionData]
    
    @validator('sections')
    def validate_sections(cls, v):
        """Validate section structure and numbering"""
        if not v:
            raise ValueError("Framework must contain at least one section")
        
        section_numbers = [section.section_number for section in v.values()]
        if sorted(section_numbers) != list(range(1, len(section_numbers) + 1)):
            raise ValueError("Section numbers must be consecutive starting from 1")
        
        return v


class FrameworkLoader:
    """
    Manages framework loading, validation, and version compatibility
    """
    
    def __init__(self):
        self.framework_cache: Optional[FrameworkData] = None
        self.framework_path = os.path.join(
            os.path.dirname(__file__), 
            "framework.yaml"
        )
    
    def load_current(self) -> FrameworkData:
        """Load current framework version"""
        if self.framework_cache is None:
            self.framework_cache = self._load_framework(self.framework_path)
        return self.framework_cache
    
    def load_for_session(self, session_id: str, required_version: str = None) -> FrameworkData:
        """
        Load framework version compatible with session
        For MVP, we only have one version
        """
        framework = self.load_current()
        
        if required_version and framework.metadata.version != required_version:
            logger.warning(
                f"Framework version mismatch - session_id: {session_id}, required_version: {required_version}, current_version: {framework.metadata.version}"
            )
        
        return framework
    
    def _load_framework(self, file_path: str) -> FrameworkData:
        """Load and validate framework from YAML file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                raw_data = yaml.safe_load(file)
            
            # Restructure data for Pydantic validation
            structured_data = self._structure_framework_data(raw_data)
            
            # Validate with Pydantic
            framework = FrameworkData(**structured_data)
            
            logger.info(
                f"Framework loaded successfully - version: {framework.metadata.version}, sections: {framework.metadata.total_sections}"
            )
            
            return framework
            
        except FileNotFoundError:
            logger.error(f"Framework file not found: {file_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            raise
        except Exception as e:
            logger.error(f"Framework loading error: {e}")
            raise
    
    def _structure_framework_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert YAML structure to Pydantic-compatible format"""
        framework_data = raw_data.get('framework', {})
        
        # Extract metadata
        metadata = framework_data.get('metadata', {})
        
        # Extract and structure sections
        sections = {}
        for key, value in framework_data.items():
            if key.startswith('section_'):
                section_number = int(key.split('_')[1])
                
                # Structure criteria
                criteria = {}
                for criterion_name, criterion_data in value.get('criteria', {}).items():
                    criteria[criterion_name] = CriterionData(**criterion_data)
                
                # Create section
                section_data = SectionData(
                    name=value['name'],
                    section_number=section_number,
                    objective=value['objective'],
                    estimated_time=value['estimated_time'],
                    criteria=criteria
                )
                
                sections[key] = section_data
        
        return {
            'metadata': FrameworkMetadata(**metadata),
            'sections': sections
        }
    
    def get_criterion(self, section_number: int, criterion_name: str) -> Optional[CriterionData]:
        """Get specific criterion by section and name"""
        framework = self.load_current()
        
        section_key = f"section_{section_number}"
        if section_key in framework.sections:
            section = framework.sections[section_key]
            return section.criteria.get(criterion_name)
        
        return None
    
    def get_section(self, section_number: int) -> Optional[SectionData]:
        """Get section by number"""
        framework = self.load_current()
        section_key = f"section_{section_number}"
        return framework.sections.get(section_key)
    
    def get_section_overview(self) -> str:
        """Get overview of all sections for greeting"""
        framework = self.load_current()
        overview_parts = []
        
        for i in range(1, framework.metadata.total_sections + 1):
            section = self.get_section(i)
            if section:
                overview_parts.append(f"Section {i}: {section.name}")
        
        return "; ".join(overview_parts)
    
    def validate_framework_integrity(self) -> bool:
        """Validate framework structure and completeness"""
        try:
            framework = self.load_current()
            
            # Check all sections have criteria
            for section_name, section in framework.sections.items():
                if not section.criteria:
                    logger.error(f"Section {section_name} has no criteria")
                    return False
                
                # Check criteria structure
                for criterion_name, criterion in section.criteria.items():
                    if not all([
                        criterion.question,
                        criterion.good_example,
                        criterion.bad_example,
                        criterion.threshold > 0
                    ]):
                        logger.error(f"Incomplete criterion: {criterion_name}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Framework validation failed: {e}")
            return False


# Global framework loader instance
framework_loader = FrameworkLoader()
